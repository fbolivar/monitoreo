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

        params = recurso.parametros or {}
        base_url = (recurso.hostname or "").strip()
        if not base_url:
            return ResultadoProbe(False, "unknown", None, [], {"error": "sitio sin URL"})

        path = params.get("http_path", "")
        url = base_url.rstrip("/") + path if path else base_url
        expected = int(params.get("expected_status", 200))
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
        detalle: dict = {"url": url, "esperado": expected}

        t0 = time.perf_counter()
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True, auth=auth, headers=headers)
        except Exception as e:
            latencia = round((time.perf_counter() - t0) * 1000, 2)
            return ResultadoProbe(False, "down", None,
                                  [Muestra("latency", latencia, "ms")],
                                  {**detalle, "error": str(e)})

        latencia = round((time.perf_counter() - t0) * 1000, 2)
        metricas.append(Muestra("latency", latencia, "ms"))
        metricas.append(Muestra("http_status", float(resp.status_code), ""))
        detalle["http_status"] = resp.status_code

        estado_base = "up"
        if resp.status_code != expected:
            estado_base = "down"
            detalle["motivo"] = f"status {resp.status_code} != esperado {expected}"
        elif match_text and match_text not in resp.text:
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
