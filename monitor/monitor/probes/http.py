"""Probe HTTP/HTTPS para sitios web: código de respuesta, latencia y días
restantes del certificado SSL."""
from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from .base import Muestra, ResultadoProbe


def _ssl_dias_restantes(host: str, port: int, timeout: float):
    """Devuelve (dias_restantes, fecha_exp) del certificado del servidor."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
    # 'notAfter' p.ej. 'Jun  1 12:00:00 2026 GMT'
    exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    dias = (exp - datetime.now(timezone.utc)).days
    return dias, exp


class HttpProbe:
    nombre = "http"
    requiere_secretos = True  # puede necesitar basic-auth o api_key

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        import httpx  # import diferido

        params = recurso.parametros if isinstance(recurso.parametros, dict) else {}
        base_url = (recurso.hostname or "").strip()
        if not base_url:
            return ResultadoProbe(False, "unknown", None, [], {"error": "sitio sin URL"})

        path = params.get("http_path", "")
        url = base_url.rstrip("/") + path if path else base_url
        # expected_status: si se define, se exige ese código EXACTO (modo estricto).
        # Si NO se define, se clasifica por familia: 2xx/3xx=up, 4xx=degraded, 5xx=down.
        expected = params.get("expected_status")
        # codigos_ok: lista opcional de códigos que cuentan como "up" (p.ej. una API
        # cuya raíz responde 404 pero está sana). Tiene prioridad sobre la familia.
        codigos_ok = params.get("codigos_ok")
        seguir = params.get("seguir_redirecciones", True)
        timeout = params.get("timeout_ms", settings.probe_timeout_ms) / 1000
        match_text = params.get("match_text")

        auth = None
        headers: dict[str, str] = {}
        if secretos:
            if "basic_auth_user" in secretos:
                auth = (secretos["basic_auth_user"], secretos.get("basic_auth_pass", ""))
            if "api_key" in secretos:
                headers["Authorization"] = f"Bearer {secretos['api_key']}"

        metricas: list[Muestra] = []
        detalle: dict = {"url": url, "esperado": expected if expected is not None else "2xx/3xx"}

        t0 = time.perf_counter()
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=bool(seguir), auth=auth, headers=headers)
        except Exception as e:
            latencia = round((time.perf_counter() - t0) * 1000, 2)
            return ResultadoProbe(False, "down", None,
                                  [Muestra("latency", latencia, "ms")],
                                  {**detalle, "error": str(e)})

        latencia = round((time.perf_counter() - t0) * 1000, 2)
        metricas.append(Muestra("latency", latencia, "ms"))
        metricas.append(Muestra("http_status", float(resp.status_code), ""))
        detalle["http_status"] = resp.status_code

        code = resp.status_code
        estado_base = "up"
        if codigos_ok:
            # Lista explícita de códigos sanos.
            if code in codigos_ok:
                estado_base = "up"
            elif code >= 500:
                estado_base = "down"
                detalle["motivo"] = f"status {code} (5xx)"
            else:
                estado_base = "degraded"
                detalle["motivo"] = f"status {code} no está en codigos_ok"
        elif expected is not None:
            # Modo estricto: se exige el código exacto.
            if code != int(expected):
                estado_base = "down"
                detalle["motivo"] = f"status {code} != esperado {expected}"
        else:
            # Clasificación por familia: 2xx/3xx=up, 4xx=degraded (responde pero
            # error de cliente), 5xx=down.
            if code >= 500:
                estado_base = "down"
                detalle["motivo"] = f"status {code} (5xx)"
            elif code >= 400:
                estado_base = "degraded"
                detalle["motivo"] = f"status {code} (4xx)"

        if estado_base == "up" and match_text and match_text not in resp.text:
            estado_base = "down"
            detalle["motivo"] = f"texto '{match_text}' ausente en la respuesta"

        # Vigencia del certificado SSL (solo https).
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname:
            try:
                dias, exp = _ssl_dias_restantes(parsed.hostname, parsed.port or 443, timeout)
                metricas.append(Muestra("ssl_dias_restantes", float(dias), "dias"))
                detalle["ssl_expira"] = exp.isoformat()
            except Exception as e:
                detalle["ssl_error"] = str(e)

        # alcanzable=True: hubo respuesta HTTP (aunque el status sea inesperado).
        return ResultadoProbe(True, estado_base, latencia, metricas, detalle)
