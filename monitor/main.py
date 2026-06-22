"""Entrypoint del worker de monitoreo.

Uso:
    python main.py

Arranca el pool de BD, asegura las particiones de métricas, registra un job por
recurso activo (APScheduler) y las tareas de mantenimiento, y bloquea hasta
recibir SIGINT/SIGTERM.
"""
from __future__ import annotations

import logging
import signal
import sys
from datetime import date, timedelta

from monitor.config import cargar_settings
from monitor.db import Database
from monitor.health import iniciar_health_server
from monitor.repository import asegurar_particiones
from monitor.scheduler import (
    construir_scheduler,
    registrar_tareas_internas,
    sincronizar_jobs,
)


def configurar_logging(nivel: str) -> None:
    logging.basicConfig(
        level=getattr(logging, nivel.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )


def main() -> int:
    settings = cargar_settings()
    configurar_logging(settings.log_level)
    log = logging.getLogger("monitor.main")

    if not settings.app_crypto_key:
        log.warning("APP_CRYPTO_KEY vacía: los probes que requieran secretos no podrán descifrarlos.")

    db = Database(settings)
    try:
        db.ping()
        log.info("Conexión a PostgreSQL OK.")
    except Exception:
        log.exception("No se pudo conectar a PostgreSQL. Abortando.")
        return 1

    # Asegurar particiones del mes actual y siguiente antes de escribir métricas.
    hoy = date.today()
    try:
        asegurar_particiones(db, [hoy, hoy + timedelta(days=31)])
    except Exception:
        log.exception("No se pudieron asegurar las particiones de métricas (¿migraciones aplicadas?).")

    health = iniciar_health_server(db, settings.health_port) if settings.health_enabled else None

    scheduler = construir_scheduler(settings)
    registrar_tareas_internas(scheduler, db, settings)
    scheduler.start()
    sincronizar_jobs(scheduler, db, settings)  # carga inicial de jobs
    log.info("Worker en marcha. Recursos planificados: %d.",
             len([j for j in scheduler.get_jobs() if j.id.startswith("recurso:")]))

    import threading
    stop = threading.Event()

    def _apagar(signum, _frame):
        log.info("Señal %s recibida; apagando…", signum)
        stop.set()

    signal.signal(signal.SIGINT, _apagar)
    signal.signal(signal.SIGTERM, _apagar)

    stop.wait()

    # Apagado limpio: esperar a que los chequeos EN VUELO terminen ANTES de cerrar
    # el pool de BD. Con wait=False, los jobs en curso (hasta scheduler_max_workers)
    # seguían usando un pool ya cerrado -> ráfaga de ~100 tracebacks 'PoolClosed' en
    # cada reinicio, que enmascaraba errores reales. Con wait=True terminan primero;
    # si alguno se cuelga, systemd lo acota con TimeoutStopSec (SIGKILL silencioso).
    log.info("Esperando a que terminen los chequeos en vuelo…")
    scheduler.shutdown(wait=True)
    if health:
        health.shutdown()
    db.close()
    log.info("Worker detenido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
