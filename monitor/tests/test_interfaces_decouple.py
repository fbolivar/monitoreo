"""Tests del desacople de la recolección de interfaces (gate por tiempo + escalonado)."""
from monitor.probes.snmp import _debe_recolectar_interfaces, _ultima_interfaces


def test_intervalo_cero_siempre_recolecta():
    assert _debe_recolectar_interfaces(9001, 0, ahora=100.0) is True
    assert _debe_recolectar_interfaces(9001, 0, ahora=100.1) is True


def test_primera_vez_no_recolecta_y_escalona():
    # La 1ª vez NO recolecta (evita ráfaga al arrancar) y deja un 'última vez'
    # escalonado dentro de la ventana.
    _ultima_interfaces.pop(9002, None)
    assert _debe_recolectar_interfaces(9002, 300, ahora=1000.0) is False
    ult = _ultima_interfaces[9002]
    assert 1000.0 - 300 <= ult <= 1000.0


def test_recolecta_al_cumplir_el_intervalo_desde_el_escalon():
    _ultima_interfaces.pop(9003, None)
    _debe_recolectar_interfaces(9003, 300, ahora=1000.0)        # fija escalón
    ult = _ultima_interfaces[9003]
    # justo antes del intervalo: no; al cumplirlo: sí
    assert _debe_recolectar_interfaces(9003, 300, ahora=ult + 299) is False
    assert _debe_recolectar_interfaces(9003, 300, ahora=ult + 300) is True


def test_tras_recolectar_reinicia_contador():
    _ultima_interfaces.pop(9004, None)
    _debe_recolectar_interfaces(9004, 300, ahora=1000.0)
    ult = _ultima_interfaces[9004]
    assert _debe_recolectar_interfaces(9004, 300, ahora=ult + 300) is True   # recolecta
    assert _debe_recolectar_interfaces(9004, 300, ahora=ult + 450) is False  # +150 < 300


def test_recursos_distintos_se_escalonan_diferente():
    # El desfase determinista reparte los walks: dos recursos consecutivos no
    # arrancan en el mismo punto de la ventana.
    _ultima_interfaces.pop(100, None)
    _ultima_interfaces.pop(101, None)
    _debe_recolectar_interfaces(100, 300, ahora=5000.0)
    _debe_recolectar_interfaces(101, 300, ahora=5000.0)
    assert _ultima_interfaces[100] != _ultima_interfaces[101]
