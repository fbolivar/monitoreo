"""Topología L2 por LLDP: parseo PURO de la LLDP-MIB.

LLDP-MIB (1.0.8802.1.1.2.1):
  - lldpRemTable (...4.1.1.<col>.<timeMark>.<localPortNum>.<remIndex>):
      .5 chassisId · .7 portId · .8 portDesc · .9 sysName · .10 sysDesc
  - lldpLocPortTable (...3.7.1.<col>.<localPortNum>):
      .3 portId · .4 portDesc  (nombre del puerto LOCAL)

La E/S (SNMP walk) la hace el runner con snmp_client; aquí solo se transforma
la lista de (oid, valor) en vecinos. `valor` puede ser str o bytes.
"""
from __future__ import annotations

# Columnas de lldpRemTable.
REM_BASE = "1.0.8802.1.1.2.1.4.1.1"
REM_CHASSIS = f"{REM_BASE}.5"
REM_PORTID = f"{REM_BASE}.7"
REM_PORTDESC = f"{REM_BASE}.8"
REM_SYSNAME = f"{REM_BASE}.9"
REM_SYSDESC = f"{REM_BASE}.10"

# Columnas de lldpLocPortTable (nombre del puerto local).
LOC_PORTID = "1.0.8802.1.1.2.1.3.7.1.3"
LOC_PORTDESC = "1.0.8802.1.1.2.1.3.7.1.4"


def _texto(valor) -> str:
    if isinstance(valor, bytes):
        return valor.decode("utf-8", "ignore").strip()
    return str(valor).strip()


def fmt_chassis(valor) -> str:
    """Formatea un chassis-id: MAC si parece 6 octetos, si no texto/hex."""
    b: bytes | None = None
    if isinstance(valor, bytes):
        b = valor
    else:
        s = str(valor)
        # pysnmp suele imprimir OctetString como '0x001122...' o como texto.
        if s.startswith("0x"):
            try:
                b = bytes.fromhex(s[2:])
            except ValueError:
                b = None
    if b is not None and len(b) == 6:
        return ":".join(f"{x:02x}" for x in b)
    if b is not None:
        # Otros subtipos (p.ej. nombre): si es imprimible, devuélvelo como texto.
        txt = b.decode("utf-8", "ignore").strip()
        return txt or ":".join(f"{x:02x}" for x in b)
    return _texto(valor)


def _suffix(oid: str, base: str) -> tuple[int, ...]:
    """Devuelve el índice (tupla de enteros) tras la base, o () si no encaja."""
    if not oid.startswith(base + "."):
        return ()
    resto = oid[len(base) + 1:]
    try:
        return tuple(int(x) for x in resto.split("."))
    except ValueError:
        return ()


def parse_puertos_locales(walk_portid: list, walk_portdesc: list) -> dict[int, str]:
    """lldpLocPortTable -> {localPortNum: nombre}. Prefiere portDesc, cae a portId."""
    locales: dict[int, str] = {}
    for base, datos in ((LOC_PORTID, walk_portid), (LOC_PORTDESC, walk_portdesc)):
        for oid, val in datos or []:
            idx = _suffix(oid, base)
            if len(idx) == 1:
                txt = _texto(val)
                # portDesc (segunda pasada) tiene prioridad si aporta algo.
                if txt and (base == LOC_PORTDESC or idx[0] not in locales):
                    locales[idx[0]] = txt
    return locales


def parse_vecinos(walks: dict[str, list], puertos_locales: dict[int, str] | None = None) -> list[dict]:
    """Construye la lista de vecinos LLDP.

    `walks` = {'sysname':[(oid,val)], 'portid':[...], 'portdesc':[...],
               'chassis':[...], 'sysdesc':[...]}. El índice de cada fila es
    (timeMark, localPortNum, remIndex); se agrupa por (localPortNum, remIndex).
    """
    puertos_locales = puertos_locales or {}
    columnas = {
        "sysname": (REM_SYSNAME, _texto),
        "portid": (REM_PORTID, _texto),
        "portdesc": (REM_PORTDESC, _texto),
        "chassis": (REM_CHASSIS, fmt_chassis),
        "sysdesc": (REM_SYSDESC, _texto),
    }

    filas: dict[tuple[int, int], dict] = {}
    orden: list[tuple[int, int]] = []
    for clave, (base, conv) in columnas.items():
        for oid, val in walks.get(clave, []) or []:
            idx = _suffix(oid, base)
            if len(idx) < 3:
                continue
            local_port_num, rem_index = idx[-2], idx[-1]
            k = (local_port_num, rem_index)
            if k not in filas:
                filas[k] = {"local_port_num": local_port_num}
                orden.append(k)
            filas[k][clave] = conv(val)

    vecinos: list[dict] = []
    for k in orden:
        f = filas[k]
        lpn = f.get("local_port_num")
        vecinos.append({
            "local_port_num": lpn,
            "local_port": puertos_locales.get(lpn),
            "remote_sysname": f.get("sysname"),
            "remote_chassis": f.get("chassis"),
            "remote_port": f.get("portdesc") or f.get("portid"),
            "remote_sysdesc": f.get("sysdesc"),
        })
    return vecinos
