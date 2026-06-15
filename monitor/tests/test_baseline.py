"""Tests de la detección de anomalías por línea base (baseline.py)."""
from monitor.baseline import Anomalia, evaluar_anomalia, media_desviacion


# ── media/desviación ──────────────────────────────────────────────────
def test_media_desviacion_basica():
    media, desv = media_desviacion([10, 12, 14, 16, 18])
    assert media == 14.0
    assert round(desv, 3) == round(((sum((x - 14) ** 2 for x in [10, 12, 14, 16, 18])) / 4) ** 0.5, 3)


def test_un_solo_punto_desviacion_cero():
    assert media_desviacion([42]) == (42.0, 0.0)


def test_serie_constante_desviacion_cero():
    assert media_desviacion([50, 50, 50]) == (50.0, 0.0)


# ── evaluar_anomalia ──────────────────────────────────────────────────
def test_valor_dentro_de_banda_no_es_anomalia():
    # media 50, σ 5, k 3 -> banda 15; 60 < 65 -> normal
    assert evaluar_anomalia("cpu", 60, 50, 5, k=3, piso=5) is None


def test_valor_fuera_de_banda_es_anomalia():
    # media 50, σ 5, k 3 -> banda 15; 70 > 65 -> anomalía
    a = evaluar_anomalia("cpu", 70, 50, 5, k=3, piso=5)
    assert isinstance(a, Anomalia)
    assert a.metrica == "cpu"
    assert round(a.z, 1) == 4.0  # (70-50)/5


def test_solo_alerta_hacia_arriba():
    # Caer por debajo de lo normal NO es anomalía.
    assert evaluar_anomalia("cpu", 10, 50, 5, k=3, piso=5) is None


def test_piso_protege_metricas_estables():
    # σ casi 0: sin piso, cualquier subida marcaría anomalía. Con piso=5, 52 es normal.
    assert evaluar_anomalia("mem", 52, 50, 0.1, k=3, piso=5) is None
    # pero 56 (> 50+5) sí supera el piso.
    a = evaluar_anomalia("mem", 56, 50, 0.1, k=3, piso=5)
    assert a is not None
    assert a.z is None or a.z > 0  # σ pequeña; z grande o None si σ=0


def test_sigma_cero_usa_piso_y_z_none():
    a = evaluar_anomalia("mem", 60, 50, 0.0, k=3, piso=5)
    assert a is not None
    assert a.z is None          # no se puede normalizar con σ=0
    assert a.banda == 5         # max(3*0, 5)
