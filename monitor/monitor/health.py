"""Endpoint /health opcional (sin dependencias extra: http.server en un hilo)."""
from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import Database

log = logging.getLogger(__name__)


def iniciar_health_server(db: Database, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path not in ("/health", "/"):
                self.send_response(404)
                self.end_headers()
                return
            try:
                ok = db.ping()
            except Exception:
                ok = False
            estado = 200 if ok else 503
            cuerpo = json.dumps({"status": "ok" if ok else "degraded", "db": ok}).encode()
            self.send_response(estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *args):  # silenciar logs de acceso
            return

    servidor = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True, name="health")
    hilo.start()
    log.info("Health server escuchando en :%s/health", port)
    return servidor
