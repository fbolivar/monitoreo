"""Probe SNMP (v2c/v3) para switches LAN, servidores, NAS, switches SAN y UPS.

- Equipos genéricos: consulta los OIDs definidos en `parametros.oids`
  ({nombre_metrica: oid}) y los guarda como métricas con ese nombre.
- UPS: usa OIDs estándar UPS-MIB (RFC 1628) → carga, % batería, autonomía,
  estado de línea, estado de batería.

La E/S vive en snmp_client.py. Aquí: selección de OIDs, credenciales y mapeo de
valores a métricas (funciones puras, testeables sin red).
"""
from __future__ import annotations

import time

from .base import Muestra, ResultadoProbe
from .snmp_client import Credenciales, snmp_get

# Reachability
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"

# UPS-MIB (RFC 1628) — nombre de métrica -> OID escalar
UPS_OIDS: dict[str, str] = {
    "battery_status": "1.3.6.1.2.1.33.1.2.1.0",   # 1 unknown,2 normal,3 low,4 depleted
    "autonomia_min":  "1.3.6.1.2.1.33.1.2.3.0",   # minutos restantes estimados
    "bateria":        "1.3.6.1.2.1.33.1.2.4.0",   # % carga restante
    "estado_linea":   "1.3.6.1.2.1.33.1.4.1.0",   # outputSource: 3 normal,5 battery,4 bypass...
    "carga":          "1.3.6.1.2.1.33.1.4.4.1.5.1",  # % carga de la salida (línea 1)
}

_UPS_UNIDADES = {
    "bateria": "%",
    "autonomia_min": "min",
    "carga": "%",
    "estado_linea": None,
    "battery_status": None,
}


def a_float(valor: object) -> float | None:
    """Convierte un valor SNMP (entero/gauge/timeticks/cadena) a float, o None."""
    if valor is None:
        return None
    try:
        return float(int(valor))  # tipos pysnmp soportan int()
    except (TypeError, ValueError):
        try:
            return float(str(valor))
        except (TypeError, ValueError):
            return None


def construir_credenciales(params: dict, secretos: dict | None) -> Credenciales | None:
    """Arma las credenciales SNMP desde parámetros (en claro) + secretos (cifrados)."""
    secretos = secretos or {}
    version = str(params.get("snmp_version", "2c"))

    if version in ("1", "2c"):
        community = secretos.get("snmp_community") or params.get("community")
        if not community:
            return None
        return Credenciales(version=version, community=community)

    # v3
    user = secretos.get("snmp_user")
    if not user:
        return None
    return Credenciales(
        version="3",
        user=user,
        auth_key=secretos.get("snmp_auth"),
        priv_key=secretos.get("snmp_priv"),
        auth_proto=str(params.get("auth_protocol", "SHA")),
        priv_proto=str(params.get("priv_protocol", "AES")),
    )


def construir_muestras_ups(valores: dict[str, object]) -> list[Muestra]:
    muestras: list[Muestra] = []
    for nombre, unidad in _UPS_UNIDADES.items():
        v = a_float(valores.get(nombre))
        if v is not None:
            muestras.append(Muestra(nombre, v, unidad))
    return muestras


def construir_muestras_generico(valores: dict[str, object], oids_map: dict[str, str]) -> list[Muestra]:
    muestras: list[Muestra] = []
    for nombre in oids_map:
        v = a_float(valores.get(nombre))
        if v is not None:
            muestras.append(Muestra(nombre, v, None))
    return muestras


class SnmpProbe:
    nombre = "snmp"
    requiere_secretos = True

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        params = recurso.parametros or {}
        host = recurso.hostname
        if not host:
            return ResultadoProbe(False, "unknown", None, [], {"error": "recurso sin hostname/IP"})

        cred = construir_credenciales(params, secretos)
        if cred is None:
            return ResultadoProbe(False, "unknown", None, [],
                                  {"error": "faltan credenciales SNMP (community o usuario v3)"})

        port = int(params.get("port", 161))
        timeout = params.get("timeout_ms", settings.probe_timeout_ms) / 1000
        retries = int(params.get("snmp_retries", 1))

        es_ups = recurso.tipo_codigo == "ups" or params.get("perfil") == "ups"
        oids_metricas = UPS_OIDS if es_ups else dict(params.get("oids", {}))
        oids = {"sysUpTime": SYS_UPTIME, **oids_metricas}

        t0 = time.perf_counter()
        try:
            ok, valores, error = snmp_get(host, port, cred, oids, timeout, retries)
        except Exception as e:
            return ResultadoProbe(False, "down", None, [],
                                  {"error": str(e), "snmp_version": cred.version})
        latencia = round((time.perf_counter() - t0) * 1000, 2)

        if es_ups:
            muestras = construir_muestras_ups(valores)
        else:
            muestras = construir_muestras_generico(valores, params.get("oids", {}))

        alcanzable = valores.get("sysUpTime") is not None
        estado_base = "up" if alcanzable else "down"
        detalle = {
            "snmp_version": cred.version,
            "nivel_seguridad": cred.nivel_seguridad(),
            "oids_consultados": list(oids_metricas.keys()),
            "oids_sin_respuesta": [n for n in oids if valores.get(n) is None],
        }
        if error:
            detalle["error"] = error
        if not alcanzable and "error" not in detalle:
            detalle["motivo"] = "sin respuesta SNMP"

        return ResultadoProbe(alcanzable, estado_base, latencia, muestras, detalle)
