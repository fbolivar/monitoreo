"""Tests de la lógica de reportes programados (due + generación CSV/PDF)."""
from datetime import datetime, timezone

from monitor.reportes import (
    generar_csv, generar_pdf, kpis, rango_segundos, reporte_due,
)


def _dt(y, m, d, h=6):
    return datetime(y, m, d, h, 0, tzinfo=timezone.utc)


FILAS = [
    {"nombre": "SW-CORE", "tipo_nombre": "Switch", "sitio_nombre": "NC", "estado_actual": "up",
     "up": 100, "degraded": 0, "down": 0, "unknown": 0, "incidencias": 0, "disponibilidad": 100.0},
    {"nombre": "GW-WAN", "tipo_nombre": "Enlace", "sitio_nombre": None, "estado_actual": "down",
     "up": 80, "degraded": 5, "down": 15, "unknown": 0, "incidencias": 3, "disponibilidad": 85.0},
    {"nombre": "Sin datos", "tipo_nombre": "Web", "sitio_nombre": "X", "estado_actual": "unknown",
     "up": 0, "degraded": 0, "down": 0, "unknown": 10, "incidencias": 0, "disponibilidad": None},
]


# ── due ───────────────────────────────────────────────────────────────
def test_primer_envio_siempre_due():
    assert reporte_due("mensual", None, _dt(2026, 6, 15)) is True


def test_mensual_due_al_cambiar_de_mes():
    assert reporte_due("mensual", _dt(2026, 5, 31), _dt(2026, 6, 1)) is True
    assert reporte_due("mensual", _dt(2026, 6, 2), _dt(2026, 6, 20)) is False


def test_semanal_due_tras_7_dias():
    assert reporte_due("semanal", _dt(2026, 6, 1), _dt(2026, 6, 8)) is True
    assert reporte_due("semanal", _dt(2026, 6, 1), _dt(2026, 6, 6)) is False


def test_diario_due_al_cambiar_de_dia():
    assert reporte_due("diario", _dt(2026, 6, 15, 6), _dt(2026, 6, 16, 6)) is True
    assert reporte_due("diario", _dt(2026, 6, 15, 6), _dt(2026, 6, 15, 23)) is False


# ── kpis / rango ──────────────────────────────────────────────────────
def test_kpis_promedia_solo_los_con_datos():
    k = kpis(FILAS)
    assert k["recursos"] == 3
    assert k["disponibilidad_promedio"] == round((100.0 + 85.0) / 2, 3)  # ignora el None
    assert k["incidencias"] == 3


def test_rango_segundos():
    assert rango_segundos("24h") == 86400
    assert rango_segundos("30d") == 2592000
    assert rango_segundos("desconocido") == 604800  # default 7d


# ── CSV / PDF ─────────────────────────────────────────────────────────
def test_csv_tiene_cabecera_y_filas_ordenadas():
    out = generar_csv(FILAS).decode("utf-8")
    lineas = out.splitlines()
    assert "Recurso" in lineas[0] and "Disponibilidad %" in lineas[0]
    # Peor disponibilidad primero: GW-WAN (85) antes que SW-CORE (100).
    assert lineas.index([l for l in lineas if "GW-WAN" in l][0]) < \
           lineas.index([l for l in lineas if "SW-CORE" in l][0])


def test_pdf_genera_bytes_o_none():
    out = generar_pdf(FILAS, "Reporte", "últimos 30 días", "2026-06-15 06:00 UTC", kpis(FILAS))
    # fpdf2 puede no estar instalado en este entorno -> None es válido.
    if out is not None:
        assert isinstance(out, (bytes, bytearray))
        assert out[:4] == b"%PDF"
