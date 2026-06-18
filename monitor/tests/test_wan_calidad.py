"""Tests de la estimación de calidad WAN / MOS (wan_calidad.py)."""
from monitor import wan_calidad as wc


def test_mos_enlace_limpio_es_bueno():
    m = wc.mos_e_model(20, 2, 0)
    assert m >= 4.0 and wc.clasificar(m) == "buena"


def test_mos_baja_con_perdida():
    limpio = wc.mos_e_model(50, 5, 0)
    con_perdida = wc.mos_e_model(50, 5, 5)
    assert con_perdida < limpio


def test_mos_enlace_malo():
    m = wc.mos_e_model(300, 40, 8)
    assert m < 3.0 and wc.clasificar(m) == "mala"


def test_mos_acotado():
    assert wc.mos_e_model(0, 0, 0) <= 4.5
    assert wc.mos_e_model(2000, 500, 90) >= 1.0


def test_clasificar_umbrales():
    assert wc.clasificar(4.2) == "buena"
    assert wc.clasificar(3.5) == "aceptable"
    assert wc.clasificar(2.0) == "mala"
    assert wc.clasificar(None) == "mala"


def test_resumir_sin_latencia_mos_nulo():
    r = wc.resumir(None, None, 100.0, None, None)
    assert r["mos"] is None and r["calidad"] == "mala"
    assert r["loss_pct"] == 100.0


def test_resumir_redondeos():
    r = wc.resumir(23.456, 1.234, 0.0, 95.678, 10.111)
    assert r["latency_ms"] == 23.46 and r["down_mbps"] == 95.68
    assert r["mos"] is not None and r["calidad"] in ("buena", "aceptable", "mala")
