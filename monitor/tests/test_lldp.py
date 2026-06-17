"""Tests del parseo puro de la LLDP-MIB (topología L2)."""
from monitor.probes import lldp
from monitor.probes.lldp import (
    LOC_PORTDESC,
    LOC_PORTID,
    MAN_BASE,
    REM_CHASSIS,
    REM_PORTDESC,
    REM_PORTID,
    REM_SYSNAME,
    fmt_chassis,
    parse_direcciones_gestion,
    parse_puertos_locales,
    parse_vecinos,
)


# ── fmt_chassis ───────────────────────────────────────────────────────
def test_fmt_chassis_mac_bytes():
    assert fmt_chassis(b"\x00\x11\x22\xaa\xbb\xcc") == "00:11:22:aa:bb:cc"


def test_fmt_chassis_mac_hex_string():
    assert fmt_chassis("0x001122aabbcc") == "00:11:22:aa:bb:cc"


def test_fmt_chassis_texto():
    assert fmt_chassis("SW-REMOTO") == "SW-REMOTO"


# ── parse_puertos_locales ─────────────────────────────────────────────
def test_puertos_locales_prefiere_desc():
    portid = [(f"{LOC_PORTID}.1", "1"), (f"{LOC_PORTID}.2", "2")]
    portdesc = [(f"{LOC_PORTDESC}.1", "Te 1/1"), (f"{LOC_PORTDESC}.2", "Te 1/2")]
    locales = parse_puertos_locales(portid, portdesc)
    assert locales == {1: "Te 1/1", 2: "Te 1/2"}


def test_puertos_locales_cae_a_portid():
    portid = [(f"{LOC_PORTID}.5", "Gi0/5")]
    locales = parse_puertos_locales(portid, [])
    assert locales == {5: "Gi0/5"}


# ── parse_vecinos ─────────────────────────────────────────────────────
def test_parse_vecinos_basico():
    # índice = timeMark.localPortNum.remIndex (p.ej. 0.3.1 -> puerto local 3)
    walks = {
        "sysname": [(f"{REM_SYSNAME}.0.3.1", "SW-PISO1"), (f"{REM_SYSNAME}.0.7.1", "AP-WIFI")],
        "portid": [(f"{REM_PORTID}.0.3.1", "Gi1/0/24"), (f"{REM_PORTID}.0.7.1", "eth0")],
        "portdesc": [(f"{REM_PORTDESC}.0.3.1", "uplink-core")],
        "chassis": [(f"{REM_CHASSIS}.0.3.1", b"\x00\x11\x22\x33\x44\x55")],
        "sysdesc": [],
    }
    locales = {3: "Te 1/3", 7: "Te 1/7"}
    vecinos = parse_vecinos(walks, locales)
    assert len(vecinos) == 2

    v1 = next(v for v in vecinos if v["remote_sysname"] == "SW-PISO1")
    assert v1["local_port_num"] == 3
    assert v1["local_port"] == "Te 1/3"
    assert v1["remote_port"] == "uplink-core"   # portdesc tiene prioridad sobre portid
    assert v1["remote_chassis"] == "00:11:22:33:44:55"

    v2 = next(v for v in vecinos if v["remote_sysname"] == "AP-WIFI")
    assert v2["local_port"] == "Te 1/7"
    assert v2["remote_port"] == "eth0"          # sin portdesc -> cae a portid


def test_parse_direcciones_gestion_ipv4():
    # índice: timeMark.localPortNum.remIndex.subtype(1).len(4).o1.o2.o3.o4
    walk = [(f"{MAN_BASE}.0.3.1.1.4.192.168.10.1", 1),
            (f"{MAN_BASE}.0.7.1.1.4.10.0.0.5", 1)]
    d = parse_direcciones_gestion(walk)
    assert d == {(3, 1): "192.168.10.1", (7, 1): "10.0.0.5"}


def test_parse_direcciones_ignora_ipv6_y_corto():
    # subtype 2 (IPv6) o índice incompleto -> se ignora.
    walk = [(f"{MAN_BASE}.0.3.1.2.16.1.2.3.4.5.6.7.8.9.10.11.12.13.14.15.16", 1),
            (f"{MAN_BASE}.0.3.1", 1)]
    assert parse_direcciones_gestion(walk) == {}


def test_parse_vecinos_incluye_mgmt():
    walks = {"sysname": [(f"{REM_SYSNAME}.0.3.1", "SW-X")]}
    direcciones = {(3, 1): "192.168.10.9"}
    v = parse_vecinos(walks, {}, direcciones)[0]
    assert v["remote_mgmt"] == "192.168.10.9"


def test_parse_vecinos_sin_datos():
    assert parse_vecinos({}, {}) == []


def test_parse_vecinos_ignora_indice_incompleto():
    walks = {"sysname": [(f"{REM_SYSNAME}.5", "X")]}  # índice de 1 sola parte
    assert parse_vecinos(walks) == []
