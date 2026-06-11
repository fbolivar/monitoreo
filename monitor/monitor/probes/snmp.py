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
from .snmp_client import Credenciales, snmp_get, snmp_walk

# Reachability
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"

# HOST-RESOURCES-MIB (Windows/Linux): CPU por núcleo y almacenamiento (memoria).
HR_PROC_LOAD = "1.3.6.1.2.1.25.3.3.1.2"   # hrProcessorLoad (tabla por núcleo)
HR_STOR_DESCR = "1.3.6.1.2.1.25.2.3.1.3"  # hrStorageDescr
HR_STOR_SIZE = "1.3.6.1.2.1.25.2.3.1.5"   # hrStorageSize
HR_STOR_USED = "1.3.6.1.2.1.25.2.3.1.6"   # hrStorageUsed

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


def promedio_cpu(proc_walk: list[tuple[str, object]]) -> float | None:
    """Promedia hrProcessorLoad de todos los núcleos (lista de (oid, valor))."""
    vals = [a_float(v) for _oid, v in proc_walk]
    vals = [x for x in vals if x is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def indice_memoria_fisica(descr_walk: list[tuple[str, object]]) -> str | None:
    """Encuentra el índice de hrStorage cuya descripción es 'Physical Memory'."""
    for oid, val in descr_walk:
        if str(val).strip().lower() == "physical memory":
            return oid.rsplit(".", 1)[-1]
    return None


def porcentaje_memoria(size: object, used: object) -> float | None:
    s, u = a_float(size), a_float(used)
    if s is None or u is None or s <= 0:
        return None
    return round(u / s * 100, 1)


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

        # Perfil HOST-RESOURCES (Windows/Linux): CPU promedio + memoria %.
        if params.get("perfil") == "hostresources":
            return self._run_hostresources(host, port, cred, timeout, retries)

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

    def _run_hostresources(self, host, port, cred, timeout, retries) -> ResultadoProbe:
        """CPU (promedio de núcleos) y memoria (% físico) vía HOST-RESOURCES-MIB."""
        t0 = time.perf_counter()
        try:
            ok, valores, error = snmp_get(host, port, cred, {"sysUpTime": SYS_UPTIME}, timeout, retries)
            alcanzable = valores.get("sysUpTime") is not None
            muestras: list[Muestra] = []
            detalle: dict = {"snmp_version": cred.version, "perfil": "hostresources"}

            if alcanzable:
                # CPU: promedio de hrProcessorLoad
                proc, err_cpu = snmp_walk(host, port, cred, HR_PROC_LOAD, timeout, retries)
                if err_cpu:
                    detalle["error_cpu"] = err_cpu
                cpu = promedio_cpu(proc)
                if cpu is not None:
                    muestras.append(Muestra("cpu", cpu, "%"))
                    detalle["nucleos"] = len(proc)

                # Memoria: % usado de la "Physical Memory"
                descr, err_mem = snmp_walk(host, port, cred, HR_STOR_DESCR, timeout, retries)
                if err_mem:
                    detalle["error_mem"] = err_mem
                idx = indice_memoria_fisica(descr)
                if idx:
                    _okm, valm, _ = snmp_get(
                        host, port, cred,
                        {"size": f"{HR_STOR_SIZE}.{idx}", "used": f"{HR_STOR_USED}.{idx}"},
                        timeout, retries,
                    )
                    mem = porcentaje_memoria(valm.get("size"), valm.get("used"))
                    if mem is not None:
                        muestras.append(Muestra("mem", mem, "%"))
        except Exception as e:  # noqa: BLE001
            return ResultadoProbe(False, "down", None, [], {"error": str(e), "perfil": "hostresources"})

        latencia = round((time.perf_counter() - t0) * 1000, 2)
        estado_base = "up" if alcanzable else "down"
        if error and not alcanzable:
            detalle["error"] = error
        return ResultadoProbe(alcanzable, estado_base, latencia, muestras, detalle)
