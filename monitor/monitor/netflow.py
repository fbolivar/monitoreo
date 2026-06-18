"""Parseo de NetFlow v5 / v9 e IPFIX (v10) — funciones PURAS y testeables.

El FortiGate (y muchos switches) exportan flujos de tráfico por UDP. Aquí solo
se DECODIFICAN los paquetes a una lista de flujos normalizados:

    {src_ip, dst_ip, src_port, dst_port, protocolo, bytes, paquetes}

La E/S de red, la agregación y la persistencia viven en netflow_listener.py.
v9/IPFIX usan plantillas (templates) que llegan en paquetes aparte; el caller
mantiene un diccionario `templates` que se va completando entre paquetes.
"""
from __future__ import annotations

import socket
import struct

# IDs de campo compartidos por NetFlow v9 e IPFIX.
F_IN_BYTES = 1
F_IN_PKTS = 2
F_PROTOCOL = 4
F_L4_SRC_PORT = 7
F_IPV4_SRC = 8
F_L4_DST_PORT = 11
F_IPV4_DST = 12
F_IPV6_SRC = 27
F_IPV6_DST = 28

# Puertos bien conocidos -> nombre de aplicación (para agrupar el tráfico).
PUERTOS_APP: dict[int, str] = {
    20: "ftp-data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    67: "dhcp", 68: "dhcp", 69: "tftp", 80: "http", 110: "pop3", 123: "ntp",
    143: "imap", 161: "snmp", 162: "snmp-trap", 389: "ldap", 443: "https",
    445: "smb", 465: "smtps", 514: "syslog", 587: "smtp", 636: "ldaps",
    993: "imaps", 995: "pop3s", 1194: "openvpn", 1433: "mssql", 1521: "oracle",
    1812: "radius", 2055: "netflow", 3306: "mysql", 3389: "rdp", 4500: "ipsec-nat",
    5060: "sip", 5061: "sips", 5432: "postgres", 5900: "vnc", 6443: "kubernetes",
    8080: "http-alt", 8443: "https-alt", 9100: "print",
}


def app_por_puerto(src_port: int | None, dst_port: int | None) -> str:
    """Nombre de la app por el puerto 'de servicio' (el menor suele serlo)."""
    candidatos = [p for p in (dst_port, src_port) if p is not None]
    for p in sorted(candidatos):
        if p in PUERTOS_APP:
            return PUERTOS_APP[p]
    if candidatos:
        return f"port-{min(candidatos)}"
    return "otros"


def _ip(raw: bytes) -> str | None:
    try:
        if len(raw) == 4:
            return socket.inet_ntop(socket.AF_INET, raw)
        if len(raw) == 16:
            return socket.inet_ntop(socket.AF_INET6, raw)
    except OSError:
        return None
    return None


def _int(raw: bytes) -> int:
    return int.from_bytes(raw, "big") if raw else 0


def parse_packet(data: bytes, templates: dict) -> list[dict]:
    """Decodifica un datagrama NetFlow/IPFIX. `templates` se actualiza in-place."""
    if len(data) < 4:
        return []
    version = int.from_bytes(data[0:2], "big")
    if version == 5:
        return _parse_v5(data)
    if version == 9:
        return _parse_v9(data, templates)
    if version == 10:
        return _parse_ipfix(data, templates)
    return []


# ── NetFlow v5: cabecera 24 B + registros fijos de 48 B ──────────────────
def _parse_v5(data: bytes) -> list[dict]:
    if len(data) < 24:
        return []
    count = int.from_bytes(data[2:4], "big")
    flujos: list[dict] = []
    off = 24
    for _ in range(count):
        if off + 48 > len(data):
            break
        r = data[off:off + 48]
        flujos.append({
            "src_ip": _ip(r[0:4]), "dst_ip": _ip(r[4:8]),
            "paquetes": _int(r[16:20]), "bytes": _int(r[20:24]),
            "src_port": _int(r[32:34]), "dst_port": _int(r[34:36]),
            "protocolo": r[38],
        })
        off += 48
    return flujos


# ── NetFlow v9: cabecera 20 B + flowsets (templates id 0, datos id>=256) ──
def _parse_v9(data: bytes, templates: dict) -> list[dict]:
    if len(data) < 20:
        return []
    source_id = int.from_bytes(data[16:20], "big")
    flujos: list[dict] = []
    off = 20
    while off + 4 <= len(data):
        fs_id = int.from_bytes(data[off:off + 2], "big")
        fs_len = int.from_bytes(data[off + 2:off + 4], "big")
        if fs_len < 4 or off + fs_len > len(data):
            break
        cuerpo = data[off + 4:off + fs_len]
        if fs_id == 0:
            _leer_templates(cuerpo, source_id, templates, enterprise=False)
        elif fs_id == 1:
            pass  # options template: se ignora
        elif fs_id >= 256:
            campos = templates.get((source_id, fs_id))
            if campos:
                flujos.extend(_leer_datos(cuerpo, campos))
        off += fs_len
    return flujos


# ── IPFIX (v10): cabecera 16 B + sets (templates id 2, datos id>=256) ─────
def _parse_ipfix(data: bytes, templates: dict) -> list[dict]:
    if len(data) < 16:
        return []
    domain_id = int.from_bytes(data[12:16], "big")
    flujos: list[dict] = []
    off = 16
    while off + 4 <= len(data):
        set_id = int.from_bytes(data[off:off + 2], "big")
        set_len = int.from_bytes(data[off + 2:off + 4], "big")
        if set_len < 4 or off + set_len > len(data):
            break
        cuerpo = data[off + 4:off + set_len]
        if set_id == 2:
            _leer_templates(cuerpo, domain_id, templates, enterprise=True)
        elif set_id == 3:
            pass  # options template
        elif set_id >= 256:
            campos = templates.get((domain_id, set_id))
            if campos:
                flujos.extend(_leer_datos(cuerpo, campos))
        off += set_len
    return flujos


def _leer_templates(cuerpo: bytes, dominio: int, templates: dict, enterprise: bool) -> None:
    """Lee uno o más templates de un flowset/set. enterprise=True habilita el
    bit empresa de IPFIX (4 bytes extra por campo). Guarda [(tipo, longitud), ...]."""
    off = 0
    while off + 4 <= len(cuerpo):
        template_id = int.from_bytes(cuerpo[off:off + 2], "big")
        field_count = int.from_bytes(cuerpo[off + 2:off + 4], "big")
        off += 4
        campos: list[tuple[int, int]] = []
        for _ in range(field_count):
            if off + 4 > len(cuerpo):
                return
            tipo = int.from_bytes(cuerpo[off:off + 2], "big")
            longitud = int.from_bytes(cuerpo[off + 2:off + 4], "big")
            off += 4
            if enterprise and (tipo & 0x8000):
                off += 4  # número de empresa (PEN): se descarta
                tipo &= 0x7FFF
            campos.append((tipo, longitud))
        if template_id >= 256 and campos:
            templates[(dominio, template_id)] = campos


def _leer_datos(cuerpo: bytes, campos: list[tuple[int, int]]) -> list[dict]:
    """Recorre los registros de datos según los campos del template."""
    ancho = sum(l for _, l in campos)
    if ancho <= 0 or any(l == 0xFFFF for _, l in campos):
        return []  # longitud variable: no soportada (evita corromper el offset)
    flujos: list[dict] = []
    off = 0
    while off + ancho <= len(cuerpo):
        reg = cuerpo[off:off + ancho]
        f: dict = {"src_ip": None, "dst_ip": None, "src_port": None,
                   "dst_port": None, "protocolo": None, "bytes": 0, "paquetes": 0}
        p = 0
        for tipo, longitud in campos:
            val = reg[p:p + longitud]
            p += longitud
            if tipo in (F_IPV4_SRC, F_IPV6_SRC):
                f["src_ip"] = _ip(val)
            elif tipo in (F_IPV4_DST, F_IPV6_DST):
                f["dst_ip"] = _ip(val)
            elif tipo == F_L4_SRC_PORT:
                f["src_port"] = _int(val)
            elif tipo == F_L4_DST_PORT:
                f["dst_port"] = _int(val)
            elif tipo == F_PROTOCOL:
                f["protocolo"] = _int(val)
            elif tipo == F_IN_BYTES:
                f["bytes"] = _int(val)
            elif tipo == F_IN_PKTS:
                f["paquetes"] = _int(val)
        flujos.append(f)
        off += ancho
    return flujos


def clave_conversacion(f: dict) -> tuple:
    """Clave de agregación de una conversación (sin importar dirección de puertos)."""
    return (f.get("src_ip"), f.get("dst_ip"), f.get("src_port"),
            f.get("dst_port"), f.get("protocolo"))
