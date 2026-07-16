"""Tests de la lógica pura del motor de notificaciones (sin BD ni red)."""
from datetime import datetime

from monitor.models import Recurso
from monitor.notificaciones.motor import canal_aplica, construir_mensaje, severidad_alcanza


def _recurso():
    return Recurso(id=1, nombre="SRV-DB-01", hostname="10.0.1.11",
                   tipo_codigo="servidor", protocolo_default="snmp")


def test_severidad_alcanza_escala_por_severidad():
    # Canal con mínimo 'critical' solo recibe critical.
    assert severidad_alcanza("critical", "critical") is True
    assert severidad_alcanza("critical", "warning") is False
    # Canal con mínimo 'warning' recibe warning y critical, no info.
    assert severidad_alcanza("warning", "warning") is True
    assert severidad_alcanza("warning", "critical") is True
    assert severidad_alcanza("warning", "info") is False
    # Canal con mínimo 'info' recibe todo.
    assert severidad_alcanza("info", "info") is True


def test_mensaje_apertura():
    msg = construir_mensaje("apertura", _recurso(), "critical",
                            "SRV-DB-01: down (critical)", "sin respuesta")
    assert msg["evento"] == "apertura"
    assert "ABIERTA" in msg["asunto"]
    assert "[CRITICAL]" in msg["asunto"]
    assert "SRV-DB-01" in msg["texto"]
    assert "sin respuesta" in msg["texto"]
    assert msg["severidad"] == "critical"


def test_mensaje_cierre():
    msg = construir_mensaje("cierre", _recurso(), "warning", "Recurso recuperado")
    assert "RESUELTA" in msg["asunto"]


def test_mensaje_escalamiento():
    msg = construir_mensaje("escalamiento:critical", _recurso(), "critical",
                            "Escalamiento de severidad: warning -> critical")
    assert "ESCALAMIENTO" in msg["asunto"]
    assert msg["evento"] == "escalamiento:critical"


# ── Enrutamiento de canales (tipo / sitio / horario) ──────────────────
_LUN_10 = datetime(2026, 7, 13, 10, 0)   # lunes 10:00 (isoweekday=1)
_SAB_23 = datetime(2026, 7, 18, 23, 30)  # sábado 23:30 (isoweekday=6)


def test_canal_sin_filtros_recibe_todo():
    assert canal_aplica({}, "warning", "servidor", 1, _LUN_10) is True


def test_canal_filtra_por_tipo_de_recurso():
    cfg = {"tipos": ["servidor", "firewall"]}
    assert canal_aplica(cfg, "critical", "servidor", 1, _LUN_10) is True
    assert canal_aplica(cfg, "critical", "switch_lan", 1, _LUN_10) is False


def test_canal_filtra_por_sitio():
    cfg = {"sitios": [1, 7]}
    assert canal_aplica(cfg, "critical", "servidor", 7, _LUN_10) is True
    assert canal_aplica(cfg, "critical", "servidor", 3, _LUN_10) is False


def test_canal_combina_tipo_y_severidad():
    cfg = {"tipos": ["servidor"], "min_severidad": "critical"}
    assert canal_aplica(cfg, "critical", "servidor", 1, _LUN_10) is True
    assert canal_aplica(cfg, "warning", "servidor", 1, _LUN_10) is False   # severidad baja
    assert canal_aplica(cfg, "critical", "starlink", 1, _LUN_10) is False  # otro tipo


def test_canal_horario_jornada_laboral():
    cfg = {"horario": {"dias": [1, 2, 3, 4, 5], "desde": "08:00", "hasta": "18:00"}}
    assert canal_aplica(cfg, "critical", "servidor", 1, _LUN_10) is True    # lunes 10:00
    assert canal_aplica(cfg, "critical", "servidor", 1, _SAB_23) is False   # sábado


def test_canal_guardia_ventana_que_cruza_medianoche():
    # 22:00-06:00: el sábado 23:30 SÍ entra; el lunes 10:00 no.
    cfg = {"horario": {"desde": "22:00", "hasta": "06:00"}}
    assert canal_aplica(cfg, "critical", "servidor", 1, _SAB_23) is True
    assert canal_aplica(cfg, "critical", "servidor", 1, _LUN_10) is False


def test_canal_none_config_no_revienta():
    assert canal_aplica(None, "critical", "servidor", 1, _LUN_10) is True
