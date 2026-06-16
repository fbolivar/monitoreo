"""Tests del desacople de la recolección de interfaces (gate por tiempo)."""
from monitor.probes.snmp import _debe_recolectar_interfaces, _ultima_interfaces


def test_intervalo_cero_siempre_recolecta():
    assert _debe_recolectar_interfaces(9001, 0, ahora=100.0) is True
    assert _debe_recolectar_interfaces(9001, 0, ahora=100.1) is True


def test_primera_vez_recolecta_y_marca():
    _ultima_interfaces.pop(9002, None)
    assert _debe_recolectar_interfaces(9002, 300, ahora=1000.0) is True
    assert _ultima_interfaces[9002] == 1000.0


def test_dentro_del_intervalo_no_recolecta():
    _ultima_interfaces.pop(9003, None)
    assert _debe_recolectar_interfaces(9003, 300, ahora=1000.0) is True
    assert _debe_recolectar_interfaces(9003, 300, ahora=1200.0) is False  # +200s < 300
    assert _debe_recolectar_interfaces(9003, 300, ahora=1299.0) is False


def test_tras_el_intervalo_vuelve_a_recolectar():
    _ultima_interfaces.pop(9004, None)
    assert _debe_recolectar_interfaces(9004, 300, ahora=1000.0) is True
    assert _debe_recolectar_interfaces(9004, 300, ahora=1300.0) is True   # +300s == intervalo
    # y reinicia el contador desde 1300
    assert _debe_recolectar_interfaces(9004, 300, ahora=1450.0) is False


def test_recursos_independientes():
    _ultima_interfaces.pop(9005, None)
    _ultima_interfaces.pop(9006, None)
    assert _debe_recolectar_interfaces(9005, 300, ahora=500.0) is True
    # otro recurso no se ve afectado por el primero
    assert _debe_recolectar_interfaces(9006, 300, ahora=500.0) is True
