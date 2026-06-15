"""Tests de la regresión/proyección de capacidad (forecast.py) y métricas ICMP."""
from monitor.forecast import proyectar, regresion_lineal
from monitor.probes.icmp import construir_muestras_icmp


# ── Regresión lineal ──────────────────────────────────────────────────
def test_recta_perfecta():
    pend, inter, r2 = regresion_lineal([0, 2, 4, 6, 8])
    assert round(pend, 6) == 2.0
    assert round(inter, 6) == 0.0
    assert r2 == 1.0 or round(r2, 6) == 1.0


def test_serie_constante_r2_none():
    pend, inter, r2 = regresion_lineal([50, 50, 50, 50])
    assert pend == 0.0
    assert inter == 50.0
    assert r2 is None


def test_menos_de_dos_puntos():
    pend, inter, r2 = regresion_lineal([42])
    assert pend == 0.0 and inter == 42.0 and r2 is None


# ── Proyección de capacidad ───────────────────────────────────────────
def test_disco_creciente_proyecta_dias():
    # 80 -> 90 en 5 días => +2/día; del 90 actual al 100 faltan 5 días.
    p = proyectar([80, 82, 84, 86, 88, 90], techo=100.0)
    assert p.pendiente_dia > 0
    assert p.dias_restantes is not None
    assert round(p.dias_restantes) == 5
    assert p.valor_actual == 90


def test_metrica_estable_sin_proyeccion():
    p = proyectar([70, 70, 70, 70], techo=100.0)
    assert p.dias_restantes is None  # no crece -> no se llena


def test_metrica_bajando_sin_proyeccion():
    p = proyectar([90, 85, 80, 75], techo=100.0)
    assert p.pendiente_dia < 0
    assert p.dias_restantes is None


def test_ya_supero_el_techo_da_cero():
    p = proyectar([95, 97, 99, 101], techo=100.0)
    assert p.dias_restantes == 0.0


# ── Métricas ICMP enriquecidas ────────────────────────────────────────
def test_icmp_vivo_emite_latency_loss_jitter_rtt():
    ms = {m.nombre: m for m in construir_muestras_icmp(
        avg_rtt=12.3456, min_rtt=10.1, max_rtt=20.9, jitter=3.4567, loss_pct=0.0, alive=True)}
    assert set(ms) == {"latency", "loss", "jitter", "rtt_min", "rtt_max"}
    assert ms["latency"].valor == 12.35
    assert ms["jitter"].valor == 3.46
    assert ms["jitter"].unidad == "ms"
    assert ms["loss"].valor == 0.0


def test_icmp_caido_solo_loss():
    ms = construir_muestras_icmp(0, 0, 0, 0, loss_pct=100.0, alive=False)
    assert len(ms) == 1
    assert ms[0].nombre == "loss" and ms[0].valor == 100.0


def test_icmp_perdida_parcial_se_reporta():
    ms = {m.nombre: m for m in construir_muestras_icmp(
        avg_rtt=50, min_rtt=40, max_rtt=80, jitter=10, loss_pct=25.0, alive=True)}
    assert ms["loss"].valor == 25.0  # responde pero con pérdida -> umbrales/reglas deciden degraded
