"""Tests de las funciones puras del probe SNMP (sin red ni pysnmp)."""
from monitor.probes.snmp import (
    a_float,
    construir_credenciales,
    construir_muestras_generico,
    construir_muestras_ups,
    indice_memoria_fisica,
    porcentaje_memoria,
    promedio_cpu,
)
from monitor.probes.snmp_client import Credenciales


def test_a_float_varios_tipos():
    assert a_float(42) == 42.0
    assert a_float("85") == 85.0
    assert a_float(None) is None
    assert a_float("no-numerico") is None


def test_credenciales_v2c_desde_secretos():
    cred = construir_credenciales({"snmp_version": "2c"}, {"snmp_community": "publica"})
    assert cred is not None
    assert cred.version == "2c"
    assert cred.community == "publica"
    assert cred.nivel_seguridad() == "n/a"


def test_credenciales_v2c_sin_community_es_none():
    assert construir_credenciales({"snmp_version": "2c"}, {}) is None


def test_credenciales_v3_authpriv():
    cred = construir_credenciales(
        {"snmp_version": "3", "auth_protocol": "SHA", "priv_protocol": "AES"},
        {"snmp_user": "monitor", "snmp_auth": "authpass", "snmp_priv": "privpass"},
    )
    assert cred.version == "3"
    assert cred.nivel_seguridad() == "authPriv"


def test_credenciales_v3_authnopriv():
    cred = construir_credenciales(
        {"snmp_version": "3"},
        {"snmp_user": "monitor", "snmp_auth": "authpass"},
    )
    assert cred.nivel_seguridad() == "authNoPriv"


def test_credenciales_v3_sin_usuario_es_none():
    assert construir_credenciales({"snmp_version": "3"}, {}) is None


def test_muestras_ups_mapea_bateria_y_carga():
    valores = {
        "battery_status": 2,
        "autonomia_min": 35,
        "bateria": 88,
        "estado_linea": 3,
        "carga": 42,
        "sysUpTime": 123456,  # no debe convertirse en métrica UPS
    }
    muestras = {m.nombre: (m.valor, m.unidad) for m in construir_muestras_ups(valores)}
    assert muestras["bateria"] == (88.0, "%")
    assert muestras["autonomia_min"] == (35.0, "min")
    assert muestras["carga"] == (42.0, "%")
    assert muestras["estado_linea"] == (3.0, None)
    assert "sysUpTime" not in muestras


def test_muestras_genericas_solo_oids_configurados():
    oids = {"cpu": "1.3.6.1.4.1.2021.11.10.0", "mem": "1.3.6.1.4.1.2021.4.6.0"}
    valores = {"cpu": 73, "mem": 60, "sysUpTime": 9999}
    muestras = {m.nombre: m.valor for m in construir_muestras_generico(valores, oids)}
    assert muestras == {"cpu": 73.0, "mem": 60.0}


def test_credenciales_es_tipo_dataclass():
    cred = Credenciales(version="2c", community="x")
    assert cred.nivel_seguridad() == "n/a"


# ── HOST-RESOURCES (Windows/Linux) ────────────────────────────────────
def test_promedio_cpu():
    walk = [
        ("1.3.6.1.2.1.25.3.3.1.2.3", 0),
        ("1.3.6.1.2.1.25.3.3.1.2.4", 10),
        ("1.3.6.1.2.1.25.3.3.1.2.5", 20),
    ]
    assert promedio_cpu(walk) == 10.0
    assert promedio_cpu([]) is None


def test_indice_memoria_fisica():
    descr = [
        ("1.3.6.1.2.1.25.2.3.1.3.1", "C:\\ Label:  Serial Number f0eb1090"),
        ("1.3.6.1.2.1.25.2.3.1.3.10", "Virtual Memory"),
        ("1.3.6.1.2.1.25.2.3.1.3.11", "Physical Memory"),
    ]
    assert indice_memoria_fisica(descr) == "11"
    assert indice_memoria_fisica([("x.1", "C:\\")]) is None


def test_porcentaje_memoria():
    # size=1309992, used=862898 -> ~65.9 %
    assert porcentaje_memoria(1309992, 862898) == 65.9
    assert porcentaje_memoria(0, 5) is None
    assert porcentaje_memoria(None, 5) is None
