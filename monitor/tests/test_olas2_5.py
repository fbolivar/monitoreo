"""Tests de los módulos puros de las olas 2–5: remediación, cumplimiento, correlación."""
from datetime import datetime, timedelta, timezone

from monitor import correlacion as corr
from monitor import cumplimiento as cmp
from monitor import remediacion as rem


# ── Remediación (#5) ──────────────────────────────────────────────────
def test_runbook_coincide_por_severidad_minima():
    rb = {"activo": True, "trigger_severidad": "critical"}
    assert rem.runbook_coincide(rb, {"severidad": "critical", "titulo": "x"})
    assert not rem.runbook_coincide(rb, {"severidad": "warning", "titulo": "x"})


def test_runbook_coincide_por_tipo_y_match():
    rb = {"activo": True, "trigger_tipo_id": 3, "trigger_match": "puerto"}
    assert rem.runbook_coincide(rb, {"tipo_id": 3, "severidad": "warning", "titulo": "SW: puerto caído"})
    assert not rem.runbook_coincide(rb, {"tipo_id": 9, "severidad": "warning", "titulo": "SW: puerto caído"})
    assert not rem.runbook_coincide(rb, {"tipo_id": 3, "severidad": "warning", "titulo": "cpu alta"})


def test_runbook_inactivo_no_coincide():
    assert not rem.runbook_coincide({"activo": False}, {"severidad": "critical", "titulo": "x"})


def test_interpolar():
    assert rem.interpolar("reinicia {hostname}", {"hostname": "10.0.0.1"}) == "reinicia 10.0.0.1"


def test_accion_tipo_no_soportado():
    ok, sal = rem.ejecutar_accion({"tipo": "magia"}, {}, None)
    assert not ok and "no soportado" in sal


# ── Cumplimiento (#7) ─────────────────────────────────────────────────
def test_politica_contiene():
    assert cmp.evaluar_politica("set snmp v3", {"tipo": "contiene", "patron": "snmp v3"})[0]
    ok, det = cmp.evaluar_politica("set snmp v2c", {"tipo": "contiene", "patron": "snmp v3"})
    assert not ok and "No se encontró" in det


def test_politica_no_contiene():
    assert cmp.evaluar_politica("config", {"tipo": "no_contiene", "patron": "telnet"})[0]
    assert not cmp.evaluar_politica("enable telnet", {"tipo": "no_contiene", "patron": "telnet"})[0]


def test_politica_regex_y_aplica():
    assert cmp.evaluar_politica("ntp 10.0.0.1", {"tipo": "regex", "patron": r"ntp \d+\.\d+"})[0]
    assert cmp.aplica({"aplica_tipo_id": None}, 5)
    assert cmp.aplica({"aplica_tipo_id": 5}, 5)
    assert not cmp.aplica({"aplica_tipo_id": 5}, 9)


# ── Correlación (#14) ─────────────────────────────────────────────────
def _inc(id_, sitio, min_offset, recurso=None, depende=None):
    base = datetime(2026, 6, 18, tzinfo=timezone.utc)
    return {"id": id_, "sitio_id": sitio, "inicio": base + timedelta(minutes=min_offset),
            "recurso_id": recurso, "depende_de_id": depende}


def test_agrupa_misma_sede_en_ventana():
    incs = [_inc(1, 10, 0), _inc(2, 10, 1), _inc(3, 10, 2)]
    grupos = corr.agrupar(incs, ventana_seg=180)
    assert len(grupos) == 1 and len(grupos[0]) == 3


def test_no_agrupa_distinta_sede():
    grupos = corr.agrupar([_inc(1, 10, 0), _inc(2, 20, 0)], ventana_seg=180)
    assert grupos == []


def test_no_agrupa_fuera_de_ventana():
    grupos = corr.agrupar([_inc(1, 10, 0), _inc(2, 10, 30)], ventana_seg=180)
    assert grupos == []


def test_causa_raiz_por_dependencia():
    # inc 1 es el recurso 100; inc 2 y 3 dependen de 100 -> causa = inc 1.
    grupo = [_inc(1, 10, 0, recurso=100), _inc(2, 10, 1, recurso=200, depende=100),
             _inc(3, 10, 2, recurso=300, depende=100)]
    assert corr.causa_raiz(grupo)["id"] == 1
