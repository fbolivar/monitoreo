"""Chequeo sintético multipaso (monitoreo de transacción, NO intrusivo).

Ejecuta una secuencia de pasos HTTP como un usuario sintético (p.ej.
login -> consulta), con aserciones por paso (código, contenido, JSON-path) y
encadenamiento de variables (extraer un token del paso 1 y usarlo en el 2).
Captura el desglose por fases (DNS/TCP/TLS) del host de entrada y el tiempo
total por paso. Es caja-negra desde afuera: no instrumenta la app del cliente.

Opt-in: `parametros.pasos` = [ {nombre, metodo, url|path, cuerpo, headers,
  esperar_status, contiene, no_contiene, json_path:{ruta,igual|existe},
  extraer:{var:'json:a.b'|'header:Name'}, max_ms}, ... ].

El parseo/evaluación es PURO y testeable; la E/S (httpx + socket) se aísla.
"""
from __future__ import annotations

import re
import socket
import ssl
import time
from urllib.parse import urlparse

from .base import Muestra, ResultadoProbe

_VAR = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


# ── Helpers puros ──────────────────────────────────────────────────────
def json_path_get(obj, ruta: str):
    """Navega 'a.b.0.c' sobre dicts/listas. Devuelve None si no existe."""
    actual = obj
    for parte in (ruta or "").split("."):
        if parte == "":
            continue
        if isinstance(actual, dict):
            actual = actual.get(parte)
        elif isinstance(actual, list):
            try:
                actual = actual[int(parte)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return actual


def interpolar(valor, variables: dict):
    """Reemplaza {{var}} en strings (recursivo sobre dict/list). variables planas."""
    if isinstance(valor, str):
        return _VAR.sub(lambda m: str(variables.get(m.group(1), m.group(0))), valor)
    if isinstance(valor, dict):
        return {k: interpolar(v, variables) for k, v in valor.items()}
    if isinstance(valor, list):
        return [interpolar(v, variables) for v in valor]
    return valor


def evaluar_paso(paso: dict, status: int, texto: str, json_obj, ms: float) -> tuple[bool, str | None, bool]:
    """Evalúa las aserciones de un paso. Devuelve (ok, motivo, lento).

    ok=False -> fallo funcional (transacción rota -> down). lento=True -> superó
    max_ms pero pasó las aserciones (-> degraded)."""
    esperar = paso.get("esperar_status")
    if esperar:
        if status not in esperar:
            return False, f"status {status} no en {esperar}", False
    elif status >= 400:
        return False, f"status {status}", False

    contiene = paso.get("contiene")
    if contiene and contiene not in (texto or ""):
        return False, f"falta texto '{contiene}'", False

    no_contiene = paso.get("no_contiene")
    if no_contiene and no_contiene in (texto or ""):
        return False, f"texto prohibido '{no_contiene}' presente", False

    jp = paso.get("json_path")
    if jp and isinstance(jp, dict):
        val = json_path_get(json_obj, jp.get("ruta", ""))
        if jp.get("existe") and val is None:
            return False, f"json-path '{jp.get('ruta')}' ausente", False
        if "igual" in jp and str(val) != str(jp["igual"]):
            return False, f"json-path '{jp.get('ruta')}'={val} != {jp['igual']}", False

    max_ms = paso.get("max_ms")
    lento = bool(max_ms) and ms > float(max_ms)
    return True, None, lento


def extraer_variables(paso: dict, texto: str, json_obj, headers: dict) -> dict:
    """Extrae variables para los pasos siguientes. Fuente 'json:ruta' o 'header:Nombre'."""
    out: dict = {}
    for var, fuente in (paso.get("extraer") or {}).items():
        if not isinstance(fuente, str):
            continue
        if fuente.startswith("json:"):
            val = json_path_get(json_obj, fuente[5:])
        elif fuente.startswith("header:"):
            val = (headers or {}).get(fuente[7:])
        else:
            val = None
        if val is not None:
            out[var] = val
    return out


def resumir(resultados: list[dict]) -> tuple[str, list[str]]:
    """Agrega el estado de la transacción a partir de los pasos.

    down si algún paso falló (transacción rota); degraded si todos pasaron pero
    alguno fue lento; up si todo bien."""
    motivos = [f"{r['nombre']}: {r['motivo']}" for r in resultados if r.get("motivo")]
    if any(not r["ok"] for r in resultados):
        return "down", motivos
    if any(r.get("lento") for r in resultados):
        return "degraded", motivos or ["transacción lenta"]
    return "up", []


# ── E/S ────────────────────────────────────────────────────────────────
def medir_fases(host: str, port: int, https: bool, timeout: float) -> dict:
    """Mide DNS/TCP/TLS del host de entrada (ms). Best-effort; {} si falla."""
    fases: dict = {}
    try:
        t = time.perf_counter()
        socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        fases["dns_ms"] = round((time.perf_counter() - t) * 1000, 2)

        t = time.perf_counter()
        sock = socket.create_connection((host, port), timeout=timeout)
        fases["tcp_ms"] = round((time.perf_counter() - t) * 1000, 2)
        try:
            if https:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                t = time.perf_counter()
                with ctx.wrap_socket(sock, server_hostname=host):
                    fases["tls_ms"] = round((time.perf_counter() - t) * 1000, 2)
            else:
                sock.close()
        except Exception:
            pass
    except Exception:
        pass
    return fases


class SinteticoProbe:
    nombre = "sintetico"
    requiere_secretos = True

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        import httpx

        params = recurso.parametros if isinstance(recurso.parametros, dict) else {}
        pasos = params.get("pasos") or []
        base = (recurso.hostname or "").strip()
        if not pasos:
            return ResultadoProbe(False, "unknown", None, [], {"error": "sin pasos sintéticos"})

        timeout = params.get("timeout_ms", settings.probe_timeout_ms) / 1000
        seguir = params.get("seguir_redirecciones", True)

        headers_base: dict[str, str] = {}
        auth = None
        if secretos:
            if "basic_auth_user" in secretos:
                auth = (secretos["basic_auth_user"], secretos.get("basic_auth_pass", ""))
            if "api_key" in secretos:
                headers_base["Authorization"] = f"Bearer {secretos['api_key']}"

        variables: dict = dict(secretos or {})  # los secretos también son interpolables
        resultados: list[dict] = []
        total_ms = 0.0
        detalle: dict = {"pasos": resultados}

        # Fases de conexión del host de entrada (primer paso).
        primera_url = self._url(base, pasos[0])
        p = urlparse(primera_url)
        if p.hostname:
            fases = medir_fases(p.hostname, p.port or (443 if p.scheme == "https" else 80),
                                p.scheme == "https", timeout)
            detalle["fases"] = fases

        try:
            with httpx.Client(timeout=timeout, follow_redirects=bool(seguir),
                              auth=auth, headers=headers_base, verify=False) as cli:
                for i, paso in enumerate(pasos):
                    r = self._ejecutar_paso(cli, base, paso, variables, i)
                    resultados.append(r)
                    total_ms += r["ms"]
                    if not r["ok"]:
                        break  # transacción rota: no seguir
        except Exception as e:  # noqa: BLE001
            detalle["error"] = str(e)
            return ResultadoProbe(False, "down", round(total_ms, 2),
                                  self._metricas(detalle, total_ms, resultados, pasos), detalle)

        estado, motivos = resumir(resultados)
        if motivos:
            detalle["motivo"] = "; ".join(motivos)
        return ResultadoProbe(True, estado, round(total_ms, 2),
                              self._metricas(detalle, total_ms, resultados, pasos), detalle)

    def _ejecutar_paso(self, cli, base, paso, variables, i):
        nombre = paso.get("nombre") or f"Paso {i + 1}"
        metodo = (paso.get("metodo") or "GET").upper()
        url = interpolar(self._url(base, paso), variables)
        headers = interpolar(paso.get("headers") or {}, variables)
        cuerpo = interpolar(paso.get("cuerpo"), variables)

        t0 = time.perf_counter()
        try:
            kw = {"headers": headers}
            if cuerpo is not None and metodo in ("POST", "PUT", "PATCH"):
                kw["json"] = cuerpo
            resp = cli.request(metodo, url, **kw)
        except Exception as e:  # noqa: BLE001
            ms = round((time.perf_counter() - t0) * 1000, 2)
            return {"nombre": nombre, "url": url, "status": None, "ok": False,
                    "motivo": f"conexión: {e}", "ms": ms, "lento": False}

        ms = round((time.perf_counter() - t0) * 1000, 2)
        texto = resp.text
        try:
            json_obj = resp.json()
        except Exception:
            json_obj = None

        ok, motivo, lento = evaluar_paso(paso, resp.status_code, texto, json_obj, ms)
        if ok:
            variables.update(extraer_variables(paso, texto, json_obj, dict(resp.headers)))
        return {"nombre": nombre, "url": url, "status": resp.status_code, "ok": ok,
                "motivo": motivo, "ms": ms, "lento": lento}

    @staticmethod
    def _url(base: str, paso: dict) -> str:
        u = (paso.get("url") or paso.get("path") or "").strip()
        if u.startswith(("http://", "https://")):
            return u
        return base.rstrip("/") + ("/" + u.lstrip("/") if u else "")

    @staticmethod
    def _metricas(detalle, total_ms, resultados, pasos) -> list[Muestra]:
        m = [Muestra("latency", round(total_ms, 2), "ms"),
             Muestra("pasos_ok", float(sum(1 for r in resultados if r["ok"])), ""),
             Muestra("pasos_total", float(len(pasos)), "")]
        fases = detalle.get("fases") or {}
        for clave in ("dns_ms", "tcp_ms", "tls_ms"):
            if clave in fases:
                m.append(Muestra(clave, float(fases[clave]), "ms"))
        # TTFB ≈ total del primer paso (aprox. de caja-negra).
        if resultados:
            m.append(Muestra("ttfb_ms", float(resultados[0]["ms"]), "ms"))
        return m
