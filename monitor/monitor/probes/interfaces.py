"""Recolección de interfaces de red por SNMP (IF-MIB / ifXTable).

Para cada interfaz administrativamente activa devuelve estado oper, velocidad,
tráfico in/out en Mbps (calculado por delta de contadores HC de 64 bits),
utilización (% de la velocidad) y errores en el intervalo.

El delta requiere el valor anterior: se guarda en una caché a nivel de módulo
(persiste entre ciclos dentro del mismo proceso del worker). Tras un reinicio,
el primer ciclo no tiene tráfico (sin muestra previa) — es esperado.
"""
from __future__ import annotations

import time

from .snmp_client import snmp_walk

# IF-MIB / IF-MIB extendida (ifXTable)
IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
IF_ADMIN = "1.3.6.1.2.1.2.2.1.7"     # ifAdminStatus (1=up, 2=down)
IF_OPER = "1.3.6.1.2.1.2.2.1.8"      # ifOperStatus  (1=up, 2=down)
IF_IN_ERR = "1.3.6.1.2.1.2.2.1.14"   # ifInErrors
IF_OUT_ERR = "1.3.6.1.2.1.2.2.1.20"  # ifOutErrors
IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"   # ifName (ifXTable)
IF_HC_IN = "1.3.6.1.2.1.31.1.1.1.6"  # ifHCInOctets (Counter64)
IF_HC_OUT = "1.3.6.1.2.1.31.1.1.1.10"  # ifHCOutOctets
IF_HIGHSPEED = "1.3.6.1.2.1.31.1.1.1.15"  # ifHighSpeed (Mbps)

_ESTADO = {1: "up", 2: "down"}

# Caché de contadores previos: (recurso_id, if_index) -> {in, out, in_err, out_err, ts}
_cache: dict[tuple[int, int], dict] = {}


def _f(v):
    if v is None:
        return None
    try:
        return float(int(v))
    except (TypeError, ValueError):
        try:
            return float(str(v))
        except (TypeError, ValueError):
            return None


def _por_indice(walk_result) -> dict[str, object]:
    """Convierte [(oid, valor)] en {ifIndex: valor} (ifIndex = último componente)."""
    salida = {}
    for oid, val in walk_result:
        salida[oid.rsplit(".", 1)[-1]] = val
    return salida


def recolectar(recurso_id, cred, host, port, timeout, retries) -> list[dict]:
    """Devuelve el snapshot de interfaces admin-up del equipo."""
    def w(oid):
        return _por_indice(snmp_walk(host, port, cred, oid, timeout, retries)[0])

    nombre = w(IF_NAME) or w(IF_DESCR)
    admin = w(IF_ADMIN)
    oper = w(IF_OPER)
    hc_in = w(IF_HC_IN)
    hc_out = w(IF_HC_OUT)
    speed = w(IF_HIGHSPEED)
    in_err = w(IF_IN_ERR)
    out_err = w(IF_OUT_ERR)

    ahora = time.time()
    snapshot: list[dict] = []

    for idx, adm in admin.items():
        if _f(adm) != 1:  # solo interfaces habilitadas (admin up)
            continue
        op = int(_f(oper.get(idx)) or 2)
        spd = _f(speed.get(idx))
        cin, cout = _f(hc_in.get(idx)), _f(hc_out.get(idx))
        cinerr = _f(in_err.get(idx)) or 0.0
        couterr = _f(out_err.get(idx)) or 0.0

        in_mbps = out_mbps = util_in = util_out = None
        d_in_err = d_out_err = None

        key = (int(recurso_id), int(idx))
        prev = _cache.get(key)
        if prev and cin is not None and cout is not None:
            dt = ahora - prev["ts"]
            if dt > 0:
                if cin >= prev["in"]:
                    in_mbps = round((cin - prev["in"]) * 8 / dt / 1_000_000, 3)
                if cout >= prev["out"]:
                    out_mbps = round((cout - prev["out"]) * 8 / dt / 1_000_000, 3)
                if cinerr >= prev["in_err"]:
                    d_in_err = int(cinerr - prev["in_err"])
                if couterr >= prev["out_err"]:
                    d_out_err = int(couterr - prev["out_err"])
                if spd and spd > 0:
                    if in_mbps is not None:
                        util_in = round(in_mbps / spd * 100, 1)
                    if out_mbps is not None:
                        util_out = round(out_mbps / spd * 100, 1)

        _cache[key] = {"in": cin or 0.0, "out": cout or 0.0,
                       "in_err": cinerr, "out_err": couterr, "ts": ahora}

        snapshot.append({
            "if_index": int(idx),
            "if_name": str(nombre.get(idx, f"if{idx}")),
            "admin_estado": "up",
            "oper_estado": _ESTADO.get(op, "down"),
            "speed_mbps": spd,
            "in_mbps": in_mbps,
            "out_mbps": out_mbps,
            "util_in": util_in,
            "util_out": util_out,
            "in_err": d_in_err,
            "out_err": d_out_err,
        })

    snapshot.sort(key=lambda x: x["if_index"])
    return snapshot
