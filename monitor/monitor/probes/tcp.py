"""Probe TCP: verifica que un puerto acepta conexión y mide la latencia de
establecimiento. Para servicios específicos (parametros.metodo = 'tcp')."""
from __future__ import annotations

import socket
import time

from .base import Muestra, ResultadoProbe


class TcpProbe:
    nombre = "tcp"
    requiere_secretos = False

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        params = recurso.parametros or {}
        host = recurso.hostname
        port = params.get("port")

        if not host or not port:
            return ResultadoProbe(False, "unknown", None, [],
                                  {"error": "TCP requiere hostname y parametros.port"})

        timeout = params.get("timeout_ms", settings.probe_timeout_ms) / 1000
        port = int(port)

        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                latencia = round((time.perf_counter() - t0) * 1000, 2)
            return ResultadoProbe(True, "up", latencia,
                                  [Muestra("latency", latencia, "ms")],
                                  {"host": host, "puerto": port})
        except Exception as e:
            return ResultadoProbe(False, "down", None,
                                  [Muestra("loss", 100.0, "%")],
                                  {"host": host, "puerto": port, "error": str(e)})
