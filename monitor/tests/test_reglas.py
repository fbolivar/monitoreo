"""Tests del evaluador de triggers compuestos (reglas multi-condición)."""
from monitor.evaluacion import evaluar
from monitor.models import Regla
from monitor.probes.base import Muestra, ResultadoProbe
from monitor.reglas import dispara, evaluar_reglas, validar_expresion


def _regla(expr, severidad="warning", nombre="r"):
    return Regla(id=1, nombre=nombre, expresion=expr, severidad=severidad)


def test_hoja_simple():
    r = _regla({"metrica": "cpu", "op": ">", "valor": 90})
    assert dispara(r, {"cpu": 95}) is True
    assert dispara(r, {"cpu": 80}) is False


def test_and_requiere_ambas():
    r = _regla({"and": [
        {"metrica": "cpu", "op": ">", "valor": 90},
        {"metrica": "mem", "op": ">", "valor": 85},
    ]})
    assert dispara(r, {"cpu": 95, "mem": 90}) is True
    assert dispara(r, {"cpu": 95, "mem": 50}) is False


def test_or_basta_una():
    r = _regla({"or": [
        {"metrica": "loss", "op": ">", "valor": 5},
        {"metrica": "latency", "op": ">", "valor": 300},
    ]})
    assert dispara(r, {"loss": 0, "latency": 400}) is True
    assert dispara(r, {"loss": 0, "latency": 50}) is False


def test_not():
    r = _regla({"not": {"metrica": "cpu", "op": ">", "valor": 90}})
    assert dispara(r, {"cpu": 10}) is True
    assert dispara(r, {"cpu": 95}) is False


def test_metrica_ausente_no_dispara():
    # Lógica trivaluada: una métrica no medida deja la regla indeterminada (no dispara).
    r = _regla({"metrica": "cpu", "op": ">", "valor": 90})
    assert dispara(r, {"mem": 99}) is False
    # not(indeterminado) sigue siendo indeterminado -> no dispara (sin falsas alarmas).
    r_not = _regla({"not": {"metrica": "cpu", "op": ">", "valor": 90}})
    assert dispara(r_not, {"mem": 99}) is False


def test_and_con_una_ausente_no_dispara():
    r = _regla({"and": [
        {"metrica": "cpu", "op": ">", "valor": 90},
        {"metrica": "mem", "op": ">", "valor": 85},
    ]})
    assert dispara(r, {"cpu": 95}) is False  # mem ausente -> indeterminado


def test_or_con_una_verdadera_dispara_aunque_falte_otra():
    r = _regla({"or": [
        {"metrica": "cpu", "op": ">", "valor": 90},
        {"metrica": "mem", "op": ">", "valor": 85},
    ]})
    assert dispara(r, {"cpu": 95}) is True  # cpu True basta, mem ausente irrelevante


def test_evaluar_reglas_devuelve_severidad_y_descripcion():
    reglas = [
        _regla({"metrica": "cpu", "op": ">", "valor": 90}, "critical", "CPU alta"),
        _regla({"metrica": "mem", "op": ">", "valor": 90}, "warning", "Mem alta"),
    ]
    disparadas = evaluar_reglas({"cpu": 95, "mem": 50}, reglas)
    assert disparadas == [("critical", "regla 'CPU alta'")]


def test_integracion_regla_eleva_a_degraded_en_evaluar():
    res = ResultadoProbe(True, "up", 10.0, [Muestra("cpu", 95, "%"), Muestra("mem", 88, "%")], {})
    regla = _regla({"and": [
        {"metrica": "cpu", "op": ">", "valor": 90},
        {"metrica": "mem", "op": ">", "valor": 85},
    ]}, "critical", "saturacion")
    ev = evaluar(res, [], [regla])
    assert ev.estado == "degraded"
    assert ev.severidad == "critical"


def test_integracion_regla_no_dispara_mantiene_up():
    res = ResultadoProbe(True, "up", 10.0, [Muestra("cpu", 50, "%")], {})
    regla = _regla({"metrica": "cpu", "op": ">", "valor": 90})
    ev = evaluar(res, [], [regla])
    assert ev.estado == "up"


def test_regla_y_umbral_se_quedan_con_la_peor():
    from monitor.models import Umbral
    res = ResultadoProbe(True, "up", 10.0, [Muestra("cpu", 95, "%"), Muestra("temp", 40, "C")], {})
    umbral = Umbral("temp", ">", valor_warning=35, valor_critical=60, duracion_segundos=0)
    regla = _regla({"metrica": "cpu", "op": ">", "valor": 90}, "critical")
    ev = evaluar(res, [umbral], [regla])
    assert ev.estado == "degraded"
    assert ev.severidad == "critical"  # gana la regla critical sobre el umbral warning


# ── Validación del AST ────────────────────────────────────────────────
def test_validar_expresion_ok():
    assert validar_expresion({"and": [
        {"metrica": "cpu", "op": ">", "valor": 90},
        {"not": {"metrica": "mem", "op": "<", "valor": 10}},
    ]}) is None


def test_validar_expresion_rechaza_operador_invalido():
    assert validar_expresion({"metrica": "cpu", "op": "=>", "valor": 90}) is not None


def test_validar_expresion_rechaza_nodo_ambiguo():
    assert validar_expresion({"and": [], "or": []}) is not None


def test_validar_expresion_rechaza_valor_no_numerico():
    assert validar_expresion({"metrica": "cpu", "op": ">", "valor": "alto"}) is not None
