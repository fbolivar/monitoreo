"""Recolección de hardware físico (out-of-band): Redfish con fallback IPMI.

Orquesta la selección de protocolo y normaliza el resultado a (inventario,
componentes) para persistir. La E/S vive en los probes; aquí la lógica de
combinación de salud es pura/testeable.
"""
from __future__ import annotations

import logging

from .probes import ipmi_probe, redfish

log = logging.getLogger(__name__)

_ORDEN = {"down": 3, "degraded": 2, "up": 1, "unknown": 0}


def desambiguar(comps: list[dict]) -> list[dict]:
    """Hace únicos los (categoria, nombre): algunos BMC repiten nombres genéricos
    ('Temp', 'Fan'). Añade un sufijo incremental a los duplicados."""
    vistos: dict[tuple[str, str], int] = {}
    for c in comps:
        clave = (c["categoria"], c["nombre"])
        n = vistos.get(clave, 0) + 1
        vistos[clave] = n
        if n > 1:
            c["nombre"] = f"{c['nombre']} #{n}"
    return comps


def peor_estado(estados: list[str]) -> str:
    """Combina estados: down > degraded > up > unknown."""
    presentes = [e for e in estados if _ORDEN.get(e, 0) > 0]
    if not presentes:
        return "unknown"
    return max(presentes, key=lambda e: _ORDEN.get(e, 0))


def _host_sin_puerto(hostname: str | None) -> str | None:
    if not hostname:
        return None
    # Quita ':puerto' pero respeta IPv6 entre corchetes (no usado aquí).
    return hostname.split(":", 1)[0].strip() or None


def config_hardware(recurso) -> dict | None:
    """Devuelve la config opt-in `parametros.hardware` o None si no aplica."""
    cfg = (recurso.parametros or {}).get("hardware")
    return cfg if isinstance(cfg, dict) else None


def recolectar(recurso, secretos, settings) -> tuple[dict, list[dict]]:
    """Devuelve (inventario, componentes). Lanza si ningún protocolo respondió."""
    params = config_hardware(recurso) or {}
    proto = (params.get("protocolo") or "auto").lower()
    host = params.get("bmc_host") or _host_sin_puerto(recurso.hostname)
    verify = bool(params.get("verify_tls", False))
    # El BMC (iDRAC/iLO) es lento y Redfish hace muchas llamadas secuenciales;
    # por eso un timeout amplio (no el de los chequeos rápidos). El sondeo es
    # poco frecuente (HARDWARE_CHECK_SEG), así que no afecta al resto.
    timeout = params.get("timeout_ms", 30000) / 1000
    user = (secretos or {}).get("bmc_user")
    password = (secretos or {}).get("bmc_password")

    if not host or not user or not password:
        raise RuntimeError("hardware: faltan bmc_host / bmc_user / bmc_password")

    if proto in ("auto", "redfish"):
        try:
            inv, comps = _desde_redfish(host, user, password, verify, timeout)
            return inv, desambiguar(comps)
        except Exception as e:  # noqa: BLE001
            if proto == "redfish":
                raise
            log.info("Redfish falló en %s (%s); intento IPMI.", recurso.nombre, e)

    inv, comps = _desde_ipmi(host, user, password, timeout)
    return inv, desambiguar(comps)


def _desde_redfish(host, user, password, verify, timeout) -> tuple[dict, list[dict]]:
    raw = redfish.consultar(host, user, password, verify, timeout)
    inv = redfish.parse_system(raw.get("system"))
    comps = (redfish.parse_thermal(raw.get("thermal"))
             + redfish.parse_power(raw.get("power"))
             + redfish.parse_storage(raw.get("storage")))

    salud = peor_estado([inv.get("salud_global", "unknown")] + [c["estado"] for c in comps])
    inventario = {
        "fabricante": inv.get("fabricante"), "modelo": inv.get("modelo"),
        "serial": inv.get("serial"), "sku": inv.get("sku"),
        "bios_version": inv.get("bios_version"), "bmc_firmware": raw.get("bmc_firmware"),
        "cpu_modelo": inv.get("cpu_modelo"), "cpu_cantidad": inv.get("cpu_cantidad"),
        "memoria_gb": inv.get("memoria_gb"), "power_state": inv.get("power_state"),
        "salud_global": salud, "protocolo": "redfish",
        "detalle": {"host_name": inv.get("host_name")},
    }
    return inventario, comps


def _desde_ipmi(host, user, password, timeout) -> tuple[dict, list[dict]]:
    raw = ipmi_probe.consultar(host, user, password, timeout)
    comps = ipmi_probe.parse_sensor(raw.get("sensor", ""))
    fru = ipmi_probe.parse_fru(raw.get("fru", ""))
    inventario = {
        "fabricante": fru.get("fabricante"), "modelo": fru.get("modelo"),
        "serial": fru.get("serial"), "sku": fru.get("sku"),
        "bios_version": None, "bmc_firmware": None,
        "cpu_modelo": None, "cpu_cantidad": None, "memoria_gb": None,
        "power_state": None, "salud_global": ipmi_probe.salud_global(comps),
        "protocolo": "ipmi", "detalle": {},
    }
    return inventario, comps
