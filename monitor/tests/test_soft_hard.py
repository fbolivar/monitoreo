"""Tests de la máquina de estados SOFT/HARD (confirmar_estado)."""
from monitor.evaluacion import confirmar_estado


def test_estado_estable_no_transiciona():
    c = confirmar_estado("up", "up", 0, "up", max_intentos=3, recovery_intentos=1)
    assert c.estado_hard == "up"
    assert c.intentos == 0
    assert c.transicion is False


def test_down_requiere_confirmacion_no_dispara_al_primer_fallo():
    # Primer 'down' tras estar 'up': queda SOFT, el HARD sigue siendo 'up'.
    c = confirmar_estado("up", "up", 0, "down", max_intentos=3, recovery_intentos=1)
    assert c.estado_hard == "up"
    assert c.estado_candidato == "down"
    assert c.intentos == 1
    assert c.transicion is False


def test_down_se_confirma_al_tercer_chequeo():
    hard, cand, intentos = "up", "up", 0
    transiciones = []
    for _ in range(3):
        c = confirmar_estado(hard, cand, intentos, "down", max_intentos=3, recovery_intentos=1)
        hard, cand, intentos = c.estado_hard, c.estado_candidato, c.intentos
        transiciones.append(c.transicion)
    # 1º y 2º SOFT, 3º consolida HARD
    assert transiciones == [False, False, True]
    assert hard == "down"
    assert intentos == 0


def test_recuperacion_inmediata_por_defecto():
    # recovery_intentos=1: el primer 'up' cierra de inmediato.
    c = confirmar_estado("down", "down", 0, "up", max_intentos=3, recovery_intentos=1)
    assert c.estado_hard == "up"
    assert c.transicion is True


def test_recuperacion_puede_exigir_confirmacion():
    c = confirmar_estado("down", "down", 0, "up", max_intentos=3, recovery_intentos=2)
    assert c.estado_hard == "down"  # aún no confirma la recuperación
    assert c.estado_candidato == "up"
    assert c.intentos == 1
    assert c.transicion is False


def test_candidato_que_cambia_reinicia_el_contador():
    # down (intentos=2) y luego degraded: el candidato cambia, contador a 1.
    c = confirmar_estado("up", "down", 2, "degraded", max_intentos=3, recovery_intentos=1)
    assert c.estado_candidato == "degraded"
    assert c.intentos == 1
    assert c.transicion is False


def test_blip_de_recuperacion_durante_caida_pendiente_resetea():
    # Veníamos confirmando 'down' (SOFT), pero un 'up' cancela el candidato.
    c = confirmar_estado("up", "down", 2, "up", max_intentos=3, recovery_intentos=1)
    assert c.estado_hard == "up"
    assert c.estado_candidato == "up"
    assert c.intentos == 0
    assert c.transicion is False


def test_max_intentos_uno_equivale_a_inmediato():
    c = confirmar_estado("up", "up", 0, "down", max_intentos=1, recovery_intentos=1)
    assert c.estado_hard == "down"
    assert c.transicion is True
