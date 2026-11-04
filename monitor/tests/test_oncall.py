"""Tests de la lógica pura de on-call / escalado multinivel."""
from datetime import datetime, timedelta, timezone

from monitor.oncall import indice_guardia, nivel_a_disparar

INICIO = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_guardia_rota_cada_periodo():
    # 3 participantes, rotación semanal
    assert indice_guardia(3, 7, INICIO, INICIO) == 0
    assert indice_guardia(3, 7, INICIO, INICIO + timedelta(days=6, hours=23)) == 0
    assert indice_guardia(3, 7, INICIO, INICIO + timedelta(days=7)) == 1
    assert indice_guardia(3, 7, INICIO, INICIO + timedelta(days=14)) == 2
    assert indice_guardia(3, 7, INICIO, INICIO + timedelta(days=21)) == 0  # vuelve a empezar


def test_guardia_sin_participantes():
    assert indice_guardia(0, 7, INICIO, INICIO) is None
    assert indice_guardia(3, 0, INICIO, INICIO) is None


def test_guardia_antes_del_inicio():
    assert indice_guardia(3, 7, INICIO, INICIO - timedelta(days=5)) == 0


NIVELES = [
    {"orden": 1, "espera_min": 10},
    {"orden": 2, "espera_min": 20},
    {"orden": 3, "espera_min": 40},
]


def test_nivel_ninguno_antes_del_primero():
    assert nivel_a_disparar(NIVELES, 5, 0) is None


def test_nivel_primero():
    assert nivel_a_disparar(NIVELES, 12, 0)["orden"] == 1


def test_nivel_no_repite_lo_ya_escalado():
    # ya escalado el nivel 1; a los 12 min no hay nada nuevo
    assert nivel_a_disparar(NIVELES, 12, 1) is None
    # a los 22 min toca el 2
    assert nivel_a_disparar(NIVELES, 22, 1)["orden"] == 2


def test_nivel_salta_al_mas_alto_vencido():
    # si el job tardó y ya pasaron 45 min sin escalar nada, va directo al 3
    assert nivel_a_disparar(NIVELES, 45, 0)["orden"] == 3
