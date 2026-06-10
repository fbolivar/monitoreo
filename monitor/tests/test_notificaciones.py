"""Tests de la lógica pura del motor de notificaciones (sin BD ni red)."""
from monitor.models import Recurso
from monitor.notificaciones.motor import construir_mensaje, severidad_alcanza


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
