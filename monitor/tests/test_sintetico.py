"""Tests de la lógica pura del chequeo sintético multipaso."""
from monitor.probes.sintetico import (
    SinteticoProbe,
    evaluar_paso,
    extraer_variables,
    interpolar,
    json_path_get,
    resumir,
)


# ── json_path_get ─────────────────────────────────────────────────────
def test_json_path_dict_y_lista():
    obj = {"data": {"items": [{"id": 1}, {"id": 2}], "token": "abc"}}
    assert json_path_get(obj, "data.token") == "abc"
    assert json_path_get(obj, "data.items.0.id") == 1
    assert json_path_get(obj, "data.items.1.id") == 2


def test_json_path_ausente():
    assert json_path_get({"a": 1}, "a.b.c") is None
    assert json_path_get({"a": 1}, "x") is None
    assert json_path_get(None, "a") is None
    assert json_path_get([1, 2], "5") is None


# ── interpolar ────────────────────────────────────────────────────────
def test_interpolar_strings_y_dict():
    v = {"token": "XYZ", "user": "ana"}
    assert interpolar("Bearer {{token}}", v) == "Bearer XYZ"
    assert interpolar({"Authorization": "Bearer {{token}}"}, v) == {"Authorization": "Bearer XYZ"}
    assert interpolar(["{{user}}", "fijo"], v) == ["ana", "fijo"]
    # Variable inexistente se deja literal.
    assert interpolar("{{falta}}", v) == "{{falta}}"
    # No-strings pasan tal cual.
    assert interpolar(42, v) == 42


# ── evaluar_paso ──────────────────────────────────────────────────────
def test_evaluar_status_ok_por_defecto():
    ok, motivo, lento = evaluar_paso({}, 200, "hola", None, 100)
    assert ok and motivo is None and not lento


def test_evaluar_status_4xx_falla():
    ok, motivo, _ = evaluar_paso({}, 404, "", None, 10)
    assert not ok and "404" in motivo


def test_evaluar_esperar_status_explicito():
    ok, _, _ = evaluar_paso({"esperar_status": [201]}, 201, "", None, 10)
    assert ok
    ok, motivo, _ = evaluar_paso({"esperar_status": [201]}, 200, "", None, 10)
    assert not ok and "200" in motivo


def test_evaluar_contiene_y_no_contiene():
    ok, _, _ = evaluar_paso({"contiene": "Bienvenido"}, 200, "Hola Bienvenido", None, 10)
    assert ok
    ok, motivo, _ = evaluar_paso({"contiene": "Bienvenido"}, 200, "Hola", None, 10)
    assert not ok and "Bienvenido" in motivo
    ok, motivo, _ = evaluar_paso({"no_contiene": "error"}, 200, "hubo un error", None, 10)
    assert not ok and "error" in motivo


def test_evaluar_json_path():
    obj = {"estado": "ok", "n": 5}
    ok, _, _ = evaluar_paso({"json_path": {"ruta": "estado", "igual": "ok"}}, 200, "", obj, 10)
    assert ok
    ok, motivo, _ = evaluar_paso({"json_path": {"ruta": "estado", "igual": "malo"}}, 200, "", obj, 10)
    assert not ok
    ok, motivo, _ = evaluar_paso({"json_path": {"ruta": "falta", "existe": True}}, 200, "", obj, 10)
    assert not ok and "ausente" in motivo


def test_evaluar_lento():
    ok, motivo, lento = evaluar_paso({"max_ms": 500}, 200, "", None, 800)
    assert ok and lento
    ok, _, lento = evaluar_paso({"max_ms": 500}, 200, "", None, 200)
    assert ok and not lento


# ── extraer_variables ─────────────────────────────────────────────────
def test_extraer_json_y_header():
    obj = {"data": {"token": "T123"}}
    headers = {"X-Session": "S9"}
    out = extraer_variables({"extraer": {"tok": "json:data.token", "ses": "header:X-Session"}},
                            "", obj, headers)
    assert out == {"tok": "T123", "ses": "S9"}


def test_extraer_ignora_ausentes():
    out = extraer_variables({"extraer": {"x": "json:no.existe"}}, "", {}, {})
    assert out == {}


# ── resumir ───────────────────────────────────────────────────────────
def test_resumir_todo_ok():
    estado, motivos = resumir([{"nombre": "A", "ok": True}, {"nombre": "B", "ok": True}])
    assert estado == "up" and motivos == []


def test_resumir_fallo_es_down():
    estado, motivos = resumir([
        {"nombre": "Login", "ok": True},
        {"nombre": "Query", "ok": False, "motivo": "status 500"},
    ])
    assert estado == "down" and "Query: status 500" in motivos


def test_resumir_lento_es_degraded():
    estado, motivos = resumir([{"nombre": "A", "ok": True, "lento": True}])
    assert estado == "degraded" and motivos


# ── url helper ────────────────────────────────────────────────────────
def test_url_absoluta_y_relativa():
    assert SinteticoProbe._url("https://app.local", {"url": "https://otro/x"}) == "https://otro/x"
    assert SinteticoProbe._url("https://app.local", {"path": "/login"}) == "https://app.local/login"
    assert SinteticoProbe._url("https://app.local/", {"url": "api/q"}) == "https://app.local/api/q"
    assert SinteticoProbe._url("https://app.local", {}) == "https://app.local"
