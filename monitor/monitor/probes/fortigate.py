"""Probe FortiGate (API REST) para firewalls. Modela el CLÚSTER HA como un solo
recurso: consulta uso (CPU/mem/sesiones) y el estado del clúster.

Lógica de estado del clúster (propuesta sobre CLAUDE.md):
  - operativo (up)     : responde y, si hay HA, hay primario y nº de miembros
                         == ha_miembros_esperados.
  - degradado (degraded): hay primario pero faltan miembros (uno caído) ó se
                         detecta failover (primario cambió desde el último chequeo).
  - caído (down)       : sin respuesta de la API, o clúster sin primario.

La detección de failover (comparar primario actual vs anterior) la hace el runner
de forma genérica usando `detalle['ha_primary']`. Aquí: parseo puro y testeable.
"""
from __future__ import annotations

import time

from .base import Muestra, ResultadoProbe

# Claves posibles (según FortiOS) que marcan al miembro primario del clúster.
_CLAVES_PRIMARIO = ("is_root_primary", "is_primary", "primary", "is_root_master", "is_manage_primary")


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parsear_uso(data: dict | None) -> dict[str, float | None]:
    """Extrae cpu/mem/sessions del endpoint system/resource/usage."""
    resultados = (data or {}).get("results", {}) or {}

    def actual(*claves):
        for k in claves:
            v = resultados.get(k)
            if isinstance(v, list) and v:
                item = v[-1]
                return _f(item.get("current") if isinstance(item, dict) else item)
            if isinstance(v, (int, float)):
                return _f(v)
        return None

    return {
        "cpu": actual("cpu"),
        "mem": actual("mem", "memory"),
        "sessions": actual("session", "sessions"),
    }


def parsear_ha(data: dict | None, esperados: int) -> dict | None:
    """Interpreta system/ha-statistics. Devuelve None si no hay HA (standalone).

    El primario se identifica por el `serial` de NIVEL SUPERIOR de la respuesta
    (FortiOS responde por la unidad primaria del clúster). Como respaldo para
    otras versiones, también se aceptan banderas por miembro (_CLAVES_PRIMARIO).
    """
    if not data:
        return None

    miembros = data.get("results")
    if isinstance(miembros, dict):
        miembros = [miembros]
    if not isinstance(miembros, list):
        return None

    serial_primario = data.get("serial")  # unidad que responde = primaria
    info = []
    primary = None
    for m in miembros:
        serial = m.get("serial_no") or m.get("serial") or m.get("hostname")
        es_primary = (
            (serial_primario is not None and serial == serial_primario)
            or any(bool(m.get(k)) for k in _CLAVES_PRIMARIO)
        )
        info.append({"serial": serial, "hostname": m.get("hostname"), "primary": es_primary})
        if es_primary and primary is None:
            primary = serial

    n = len(miembros)
    if n == 0 or primary is None:
        estado, motivo = "down", "clúster sin primario"
    elif n < esperados:
        estado, motivo = "degraded", f"HA degradado: {n} de {esperados} miembros"
    else:
        estado, motivo = "up", None

    return {"estado": estado, "primary": primary, "miembros": info, "n": n, "motivo": motivo}


class FortiGateProbe:
    nombre = "fortigate"
    requiere_secretos = True

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        from . import fortigate_client

        params = recurso.parametros or {}
        host = recurso.hostname
        if not host:
            return ResultadoProbe(False, "unknown", None, [], {"error": "firewall sin hostname/IP"})

        token = (secretos or {}).get("api_key")
        if not token:
            return ResultadoProbe(False, "unknown", None, [], {"error": "falta api_key del FortiGate"})

        verify_ssl = bool(params.get("verify_ssl", False))
        esperados = int(params.get("ha_miembros_esperados", 2))
        timeout = params.get("timeout_ms", settings.probe_timeout_ms) / 1000

        t0 = time.perf_counter()
        try:
            datos = fortigate_client.consultar(host, token, verify_ssl, timeout)
        except Exception as e:
            return ResultadoProbe(False, "down", None, [], {"error": str(e), "fuente": "fortigate-api"})
        latencia = round((time.perf_counter() - t0) * 1000, 2)

        uso = parsear_uso(datos.get("uso"))
        ha = parsear_ha(datos.get("ha"), esperados)

        muestras: list[Muestra] = []
        if uso.get("cpu") is not None:
            muestras.append(Muestra("cpu", uso["cpu"], "%"))
        if uso.get("mem") is not None:
            muestras.append(Muestra("mem", uso["mem"], "%"))
        if uso.get("sessions") is not None:
            muestras.append(Muestra("sessions", uso["sessions"], ""))

        detalle: dict = {"fuente": "fortigate-api"}
        if ha is not None:
            estado_base = ha["estado"]
            muestras.append(Muestra("ha_miembros", float(ha["n"]), ""))
            detalle["ha_primary"] = ha["primary"]
            detalle["ha_miembros"] = ha["miembros"]
            if ha["motivo"]:
                detalle["motivo"] = ha["motivo"]
        else:
            estado_base = "up"  # standalone: respondió la API
            detalle["ha"] = "standalone"

        return ResultadoProbe(estado_base != "down", estado_base, latencia, muestras, detalle)
