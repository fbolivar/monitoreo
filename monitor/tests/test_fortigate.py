"""Tests del parseo PURO del probe FortiGate (sin red)."""
from monitor.probes.fortigate import parsear_ha, parsear_uso


def test_parsear_uso_formato_listas():
    data = {"results": {
        "cpu": [{"current": 7}],
        "mem": [{"current": 43}],
        "session": [{"current": 1820}],
    }}
    uso = parsear_uso(data)
    assert uso == {"cpu": 7.0, "mem": 43.0, "sessions": 1820.0}


def test_parsear_uso_tolera_vacio():
    assert parsear_uso(None) == {"cpu": None, "mem": None, "sessions": None}


def test_ha_operativo_dos_miembros():
    data = {"results": [
        {"serial_no": "FG1", "hostname": "fw-a", "is_root_primary": True},
        {"serial_no": "FG2", "hostname": "fw-b", "is_root_primary": False},
    ]}
    ha = parsear_ha(data, esperados=2)
    assert ha["estado"] == "up"
    assert ha["primary"] == "FG1"
    assert ha["n"] == 2


def test_ha_degradado_falta_un_miembro():
    data = {"results": [{"serial_no": "FG1", "is_primary": True}]}
    ha = parsear_ha(data, esperados=2)
    assert ha["estado"] == "degraded"
    assert "miembros" in ha["motivo"]


def test_ha_caido_sin_primario():
    data = {"results": [
        {"serial_no": "FG1", "is_root_primary": False},
        {"serial_no": "FG2", "is_root_primary": False},
    ]}
    ha = parsear_ha(data, esperados=2)
    assert ha["estado"] == "down"
    assert ha["primary"] is None


def test_ha_none_si_standalone():
    assert parsear_ha(None, esperados=2) is None
