"""Colector de NetFlow v5/v9 e IPFIX (servicio independiente: simon-netflow).

Escucha flujos en UDP/2055 (los exporta el FortiGate y los switches), los
decodifica (netflow.py), los AGREGA por conversación en ventanas de tiempo y
persiste el TOP-N por ventana en la tabla `flujos`. Mapea el exportador→recurso
por IP. No guarda flujo crudo (sería ingobernable): solo top conversaciones.

Pasa SIMON de "cuántos Mbps por puerto" a "quién consume el ancho de banda".
"""
from __future__ import annotations

import logging
import socket
import time
from datetime import datetime, timezone

from monitor import netflow
from monitor import repository as repo
from monitor.config import cargar_settings
from monitor.db import Database

log = logging.getLogger("monitor.netflow")


def _flush(db: Database, acc: dict, ventana_inicio: datetime, top_n: int,
           cache_recurso: dict) -> int:
    """Vuelca el TOP-N de conversaciones de cada exportador a la BD."""
    if not acc:
        return 0
    ahora = datetime.now(timezone.utc)
    filas: list[tuple] = []
    for exporter_ip, convs in acc.items():
        if exporter_ip not in cache_recurso:
            cache_recurso[exporter_ip] = (
                repo.recurso_id_por_host(db, exporter_ip) if exporter_ip else None)
        recurso_id = cache_recurso[exporter_ip]
        top = sorted(convs.values(), key=lambda c: c["bytes"], reverse=True)[:top_n]
        for c in top:
            filas.append((
                exporter_ip, recurso_id, ventana_inicio, ahora,
                c["src_ip"], c["dst_ip"], c["src_port"], c["dst_port"],
                c["protocolo"], netflow.app_por_puerto(c["src_port"], c["dst_port"]),
                c["bytes"], c["paquetes"],
            ))
    repo.guardar_flujos(db, filas)
    return len(filas)


def main() -> int:
    settings = cargar_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    if not settings.netflow_enabled:
        log.info("NETFLOW_ENABLED=false; colector desactivado.")
        return 0

    db = Database(settings)
    try:
        db.ping()
    except Exception:
        log.exception("No se pudo conectar a PostgreSQL. Abortando colector NetFlow.")
        return 1

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((settings.netflow_bind, settings.netflow_port))
    sock.settimeout(1.0)
    log.info("Colector NetFlow escuchando en %s:%s (flush %ss, top %s).",
             settings.netflow_bind, settings.netflow_port,
             settings.netflow_flush_seg, settings.netflow_top_n)

    templates: dict = {}                 # (source_id, template_id) -> campos
    acc: dict[str | None, dict] = {}     # exporter_ip -> {clave_conv: agregado}
    cache_recurso: dict = {}             # exporter_ip -> recurso_id
    ventana_inicio = datetime.now(timezone.utc)
    ultimo_flush = time.monotonic()

    try:
        while True:
            try:
                data, addr = sock.recvfrom(65535)
                exporter_ip = addr[0]
                try:
                    flujos = netflow.parse_packet(data, templates)
                except Exception:  # noqa: BLE001
                    log.exception("Paquete NetFlow inválido de %s", exporter_ip)
                    flujos = []
                convs = acc.setdefault(exporter_ip, {})
                for f in flujos:
                    k = netflow.clave_conversacion(f)
                    a = convs.get(k)
                    if a is None:
                        convs[k] = dict(f)
                    else:
                        a["bytes"] += f.get("bytes", 0)
                        a["paquetes"] += f.get("paquetes", 0)
            except socket.timeout:
                pass

            if time.monotonic() - ultimo_flush >= settings.netflow_flush_seg:
                try:
                    n = _flush(db, acc, ventana_inicio, settings.netflow_top_n, cache_recurso)
                    if n:
                        log.info("Flush NetFlow: %s conversaciones (%s exportadores).",
                                 n, len(acc))
                except Exception:
                    log.exception("Error volcando flujos a la BD")
                acc = {}
                ventana_inicio = datetime.now(timezone.utc)
                ultimo_flush = time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        db.close()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
