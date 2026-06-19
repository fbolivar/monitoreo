"""Tests de la lógica PURA del probe MPLS por tráfico (sin red ni BD)."""
from monitor.probes.mpls_trafico import (
    evaluar_actividad,
    extraer_ips,
    parsear_subredes,
    subredes_con_trafico,
)

SESION = """
session info: proto=6 proto_state=01
hook=pre dir=org act=noop 192.168.211.5:51234->192.168.50.2:53(0.0.0.0:0)
hook=post dir=reply act=noop 192.168.50.2:53->192.168.211.5:51234
session info: proto=17
hook=pre dir=org act=noop 192.168.9.20:1024->192.168.50.3:88(0.0.0.0:0)
"""


def test_extraer_ips():
    ips = extraer_ips(SESION)
    assert "192.168.211.5" in ips
    assert "192.168.9.20" in ips
    assert "192.168.50.2" in ips


def test_extraer_ips_descarta_invalidas():
    assert "999.1.1.1" not in extraer_ips("x 999.1.1.1 y 192.168.1.1")
    assert "192.168.1.1" in extraer_ips("x 999.1.1.1 y 192.168.1.1")


def test_parsear_subredes_ignora_invalidas():
    d = parsear_subredes([("192.168.3.0/25", 1), ("malo/99", 2), ("192.168.9.16/28", 3)])
    assert set(d) == {"192.168.3.0/25", "192.168.9.16/28"}


def test_subredes_con_trafico():
    subredes = parsear_subredes([("192.168.211.0/27", 156), ("192.168.9.16/28", 158),
                                 ("192.168.231.0/27", 81)])
    ips = {"192.168.211.5", "192.168.9.20", "192.168.50.2"}
    activas = subredes_con_trafico(ips, subredes)
    assert activas["192.168.211.0/27"] == 1
    assert activas["192.168.9.16/28"] == 1     # .9.20 sí cae en .9.16/28 (.16-.31)
    assert "192.168.231.0/27" not in activas   # sin tráfico -> caída


def test_evaluar_sin_subred_unknown():
    estado, edad, _ = evaluar_actividad(None, None, 1000.0, 1000.0, 1800)
    assert estado == "unknown"


def test_evaluar_sin_muestreo_unknown():
    estado, _, _ = evaluar_actividad("192.168.3.0/25", None, None, 1000.0, 1800)
    assert estado == "unknown"   # el job aún no ha corrido


def test_evaluar_con_trafico_reciente_up():
    estado, edad, _ = evaluar_actividad("192.168.3.0/25", 1000.0, 1100.0, 1100.0, 1800)
    assert estado == "up"
    assert edad == 100.0


def test_evaluar_trafico_viejo_down():
    estado, edad, _ = evaluar_actividad("192.168.3.0/25", 1000.0, 5000.0, 5000.0, 1800)
    assert estado == "down"
    assert edad == 4000.0


def test_evaluar_subred_sin_trafico_down():
    # Muestreo hecho (ultima_actualizacion no None) pero la subred nunca tuvo tráfico.
    estado, _, _ = evaluar_actividad("192.168.231.0/27", None, 5000.0, 5000.0, 1800)
    assert estado == "down"
