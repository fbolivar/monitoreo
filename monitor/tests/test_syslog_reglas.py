"""Tests de la evaluación pura de reglas syslog→incidencia."""
from monitor.syslog_reglas import compilar, evaluar

REGLAS = [
    {"nombre": "BGP down", "activo": True, "campo": "mensaje", "patron": r"bgp.*down",
     "accion": "abrir", "severidad": "critical", "clave": "bgp", "notificar": True},
    {"nombre": "BGP up", "activo": True, "campo": "mensaje", "patron": r"bgp.*up",
     "accion": "cerrar", "clave": "bgp", "notificar": True},
    {"nombre": "regex malo", "activo": True, "campo": "mensaje", "patron": r"(sin cerrar",
     "accion": "abrir", "severidad": "warning", "clave": "x", "notificar": False},
    {"nombre": "inactiva", "activo": False, "campo": "mensaje", "patron": r".*",
     "accion": "abrir", "severidad": "warning", "clave": "z", "notificar": False},
]


def test_compilar_omite_invalidos_e_inactivos():
    c = compilar(REGLAS)
    assert {r["nombre"] for r in c} == {"BGP down", "BGP up"}  # malo e inactiva fuera


def test_casa_abrir():
    c = compilar(REGLAS)
    m = evaluar({"mensaje": "neighbor 10.0.0.1 BGP session Down"}, c)
    assert len(m) == 1 and m[0]["accion"] == "abrir" and m[0]["clave"] == "bgp"


def test_casa_cerrar():
    c = compilar(REGLAS)
    m = evaluar({"mensaje": "BGP neighbor is Up now"}, c)
    assert len(m) == 1 and m[0]["accion"] == "cerrar"


def test_no_casa():
    c = compilar(REGLAS)
    assert evaluar({"mensaje": "interface counters cleared"}, c) == []


def test_campo_distinto_no_casa_mensaje():
    reglas = compilar([{"nombre": "x", "activo": True, "campo": "app", "patron": "sshd",
                        "accion": "abrir", "severidad": "warning", "clave": "ssh", "notificar": False}])
    assert evaluar({"mensaje": "sshd algo", "app": "kernel"}, reglas) == []   # mira app, no mensaje
    assert len(evaluar({"mensaje": "x", "app": "sshd"}, reglas)) == 1
