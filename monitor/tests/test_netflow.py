"""Tests del parser NetFlow v5/v9/IPFIX y de la clasificación por app (netflow.py)."""
import socket
import struct

from monitor import netflow


def _v5_record(src, dst, sport, dport, proto, pkts, octets):
    return (socket.inet_aton(src) + socket.inet_aton(dst) + socket.inet_aton("0.0.0.0")
            + struct.pack("!HH", 1, 2)
            + struct.pack("!II", pkts, octets)
            + struct.pack("!II", 0, 0)
            + struct.pack("!HH", sport, dport)
            + bytes([0, 0, proto, 0])
            + struct.pack("!HH", 0, 0) + bytes([0, 0, 0, 0]))


def test_v5_un_registro():
    hdr = struct.pack("!HHIIIIBBH", 5, 1, 0, 0, 0, 0, 0, 0, 0)
    pkt = hdr + _v5_record("10.0.0.5", "8.8.8.8", 50000, 443, 6, 10, 1500)
    flujos = netflow.parse_packet(pkt, {})
    assert len(flujos) == 1
    f = flujos[0]
    assert f["src_ip"] == "10.0.0.5" and f["dst_ip"] == "8.8.8.8"
    assert f["src_port"] == 50000 and f["dst_port"] == 443
    assert f["protocolo"] == 6 and f["bytes"] == 1500 and f["paquetes"] == 10


def test_v5_varios_registros():
    hdr = struct.pack("!HHIIIIBBH", 5, 2, 0, 0, 0, 0, 0, 0, 0)
    pkt = hdr + _v5_record("10.0.0.5", "8.8.8.8", 1, 53, 17, 2, 200) \
              + _v5_record("10.0.0.6", "1.1.1.1", 2, 80, 6, 5, 600)
    assert len(netflow.parse_packet(pkt, {})) == 2


def test_version_desconocida_devuelve_vacio():
    assert netflow.parse_packet(struct.pack("!H", 99) + b"\x00" * 30, {}) == []


def test_v9_template_y_datos():
    # Template flowset (id 0): template 256 con 6 campos fijos.
    campos = [(netflow.F_IPV4_SRC, 4), (netflow.F_IPV4_DST, 4),
              (netflow.F_L4_SRC_PORT, 2), (netflow.F_L4_DST_PORT, 2),
              (netflow.F_PROTOCOL, 1), (netflow.F_IN_BYTES, 4)]
    tcuerpo = struct.pack("!HH", 256, len(campos))
    for t, l in campos:
        tcuerpo += struct.pack("!HH", t, l)
    tfs = struct.pack("!HH", 0, 4 + len(tcuerpo)) + tcuerpo

    # Data flowset (id 256): un registro.
    dato = (socket.inet_aton("192.168.1.10") + socket.inet_aton("172.16.0.1")
            + struct.pack("!HH", 12345, 443) + bytes([6]) + struct.pack("!I", 9000))
    dfs = struct.pack("!HH", 256, 4 + len(dato)) + dato

    cuerpo = tfs + dfs
    hdr = struct.pack("!HHIIII", 9, 2, 0, 0, 0, 7)  # source_id=7
    templates: dict = {}
    flujos = netflow.parse_packet(hdr + cuerpo, templates)
    assert (7, 256) in templates
    assert len(flujos) == 1
    assert flujos[0]["dst_port"] == 443 and flujos[0]["bytes"] == 9000


def test_v9_datos_sin_template_se_ignoran():
    dato = b"\x00" * 15
    dfs = struct.pack("!HH", 256, 4 + len(dato)) + dato
    hdr = struct.pack("!HHIIII", 9, 1, 0, 0, 0, 1)
    assert netflow.parse_packet(hdr + dfs, {}) == []


def test_app_por_puerto():
    assert netflow.app_por_puerto(50000, 443) == "https"
    assert netflow.app_por_puerto(53, 33000) == "dns"
    assert netflow.app_por_puerto(40000, 40001).startswith("port-")
    assert netflow.app_por_puerto(None, None) == "otros"


def test_clave_conversacion_estable():
    f = {"src_ip": "a", "dst_ip": "b", "src_port": 1, "dst_port": 2, "protocolo": 6}
    assert netflow.clave_conversacion(f) == ("a", "b", 1, 2, 6)
