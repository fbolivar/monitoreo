"""Tests de la lógica PURA de evaluación de estado (sin BD ni red)."""
from monitor.evaluacion import evaluar
from monitor.models import Umbral
from monitor.probes.base import Muestra, ResultadoProbe


def _up(metricas):
    return ResultadoProbe(True, "up", 10.0, metricas, {})


def test_sin_umbrales_responde_up():
    res = _up([Muestra("latency", 10, "ms")])
    ev = evaluar(res, [])
    assert ev.estado == "up"
    assert ev.severidad is None


def test_down_es_critico():
    res = ResultadoProbe(False, "down", None, [], {"motivo": "sin respuesta"})
    ev = evaluar(res, [])
    assert ev.estado == "down"
    assert ev.severidad == "critical"


def test_unknown_es_warning():
    res = ResultadoProbe(False, "unknown", None, [], {"motivo": "no soportado"})
    ev = evaluar(res, [])
    assert ev.estado == "unknown"
    assert ev.severidad == "warning"


def test_umbral_warning_degrada():
    umbral = Umbral("latency", ">", valor_warning=80, valor_critical=200, duracion_segundos=0)
    ev = evaluar(_up([Muestra("latency", 120, "ms")]), [umbral])
    assert ev.estado == "degraded"
    assert ev.severidad == "warning"


def test_umbral_critico_degrada_con_severidad_critica():
    umbral = Umbral("latency", ">", valor_warning=80, valor_critical=200, duracion_segundos=0)
    ev = evaluar(_up([Muestra("latency", 250, "ms")]), [umbral])
    assert ev.estado == "degraded"
    assert ev.severidad == "critical"


def test_operador_menor_para_ssl_y_bateria():
    # ssl_dias_restantes < 7 => crítico
    umbral = Umbral("ssl_dias_restantes", "<", valor_warning=30, valor_critical=7, duracion_segundos=0)
    assert evaluar(_up([Muestra("ssl_dias_restantes", 5, "dias")]), [umbral]).severidad == "critical"
    assert evaluar(_up([Muestra("ssl_dias_restantes", 20, "dias")]), [umbral]).severidad == "warning"
    assert evaluar(_up([Muestra("ssl_dias_restantes", 90, "dias")]), [umbral]).estado == "up"


def test_estado_base_degraded_es_degraded_warning():
    # Un probe que ya reporta degraded (p.ej. FortiGate HA) sin superar umbrales.
    res = ResultadoProbe(True, "degraded", 10.0, [Muestra("cpu", 30, "%")],
                         {"motivo": "HA degradado: 1 de 2 miembros"})
    ev = evaluar(res, [])
    assert ev.estado == "degraded"
    assert ev.severidad == "warning"
    assert ev.motivos == ["HA degradado: 1 de 2 miembros"]


def test_estado_base_degraded_escala_a_critical_por_umbral():
    umbral = Umbral("cpu", ">", valor_warning=75, valor_critical=90, duracion_segundos=0)
    res = ResultadoProbe(True, "degraded", 10.0, [Muestra("cpu", 95, "%")], {"motivo": "HA degradado"})
    ev = evaluar(res, [umbral])
    assert ev.estado == "degraded"
    assert ev.severidad == "critical"


def test_peor_severidad_entre_varias_metricas():
    umbrales = [
        Umbral("latency", ">", 80, 200, 0),
        Umbral("loss", ">", 2, 10, 0),
    ]
    res = _up([Muestra("latency", 100, "ms"), Muestra("loss", 15, "%")])
    ev = evaluar(res, umbrales)
    # latency=warning, loss=critical -> gana critical
    assert ev.estado == "degraded"
    assert ev.severidad == "critical"
