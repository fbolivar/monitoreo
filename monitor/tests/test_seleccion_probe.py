"""Tests del selector de probe por recurso (sin red)."""
from monitor.models import Recurso
from monitor.probes import seleccionar_probe
from monitor.probes.fortigate import FortiGateProbe
from monitor.probes.http import HttpProbe
from monitor.probes.icmp import IcmpProbe
from monitor.probes.sintetico import SinteticoProbe
from monitor.probes.snmp import SnmpProbe
from monitor.probes.starlink import StarlinkProbe
from monitor.probes.tcp import TcpProbe


def _recurso(**kw):
    # Por defecto un tipo NO-SNMP (fibra_wan) para probar el fallback ICMP.
    base = dict(id=1, nombre="x", hostname="10.0.0.1", tipo_codigo="fibra_wan",
                protocolo_default="icmp", parametros={}, intervalo_segundos=60)
    base.update(kw)
    return Recurso(**base)


def test_sitio_web_usa_http():
    r = _recurso(tipo_codigo="sitio_web", hostname="https://web.local", protocolo_default="https")
    assert isinstance(seleccionar_probe(r), HttpProbe)


def test_pasos_usa_sintetico():
    # parametros.pasos tiene precedencia sobre el tipo/host.
    r = _recurso(tipo_codigo="sitio_web", hostname="https://web.local",
                 parametros={"pasos": [{"nombre": "raíz", "path": "/"}]})
    assert isinstance(seleccionar_probe(r), SinteticoProbe)


def test_url_directa_usa_http():
    r = _recurso(hostname="http://algo.local")
    assert isinstance(seleccionar_probe(r), HttpProbe)


def test_metodo_tcp_usa_tcp():
    r = _recurso(parametros={"metodo": "tcp", "port": 443})
    assert isinstance(seleccionar_probe(r), TcpProbe)


def test_firewall_usa_fortigate():
    r = _recurso(tipo_codigo="firewall", hostname="10.0.0.1")
    assert isinstance(seleccionar_probe(r), FortiGateProbe)


def test_fibra_wan_usa_icmp():
    r = _recurso(tipo_codigo="fibra_wan", hostname="8.8.8.8")
    assert isinstance(seleccionar_probe(r), IcmpProbe)


def test_starlink_usa_starlink_probe():
    r = _recurso(tipo_codigo="starlink", hostname="192.168.100.1", protocolo_default="starlink")
    assert isinstance(seleccionar_probe(r), StarlinkProbe)


def test_tipos_snmp_usan_snmp():
    for tipo in ("servidor", "switch_lan", "switch_san", "nas", "ups"):
        r = _recurso(tipo_codigo=tipo, hostname="10.0.0.9", protocolo_default="snmp")
        assert isinstance(seleccionar_probe(r), SnmpProbe), tipo


def test_metodo_snmp_explicito():
    r = _recurso(tipo_codigo="fibra_wan", parametros={"metodo": "snmp"})
    assert isinstance(seleccionar_probe(r), SnmpProbe)


def test_sin_host_no_hay_probe():
    r = _recurso(hostname=None)
    assert seleccionar_probe(r) is None
