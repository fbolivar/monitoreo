"""Planificación con APScheduler: un job por recurso según su intervalo, con
resincronización periódica y tareas de mantenimiento de datos."""
from __future__ import annotations

import logging

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import repository as repo
from .config import Settings
from .db import Database
from .notificaciones import reintentar_pendientes
from .runner import ejecutar_chequeo_por_id

log = logging.getLogger(__name__)


def construir_scheduler(settings: Settings) -> BackgroundScheduler:
    return BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(settings.scheduler_max_workers)},
        job_defaults={
            "coalesce": True,       # si se acumulan ejecuciones, corre una sola
            "max_instances": 1,     # nunca dos chequeos del mismo recurso a la vez
            "misfire_grace_time": settings.misfire_grace,
        },
        timezone="UTC",
    )


def _job_id(recurso_id: int) -> str:
    return f"recurso:{recurso_id}"


def sincronizar_jobs(scheduler: BackgroundScheduler, db: Database, settings: Settings) -> None:
    """Crea/actualiza/elimina jobs según los recursos activos en la BD."""
    recursos = repo.cargar_recursos_activos(db)
    activos = {_job_id(r.id) for r in recursos}

    # Altas y cambios de intervalo
    for r in recursos:
        jid = _job_id(r.id)
        existente = scheduler.get_job(jid)
        if existente is None:
            scheduler.add_job(
                ejecutar_chequeo_por_id,
                trigger=IntervalTrigger(seconds=r.intervalo_segundos),
                args=[db, settings, r.id],
                id=jid,
                name=f"{r.nombre} ({r.intervalo_segundos}s)",
                replace_existing=True,
                next_run_time=None,
            )
            log.info("Job alta: %s cada %ss", r.nombre, r.intervalo_segundos)
        else:
            # Si cambió el intervalo, reprogramar.
            interval = getattr(existente.trigger, "interval", None)
            if interval is not None and int(interval.total_seconds()) != r.intervalo_segundos:
                scheduler.reschedule_job(jid, trigger=IntervalTrigger(seconds=r.intervalo_segundos))
                log.info("Job reprogramado: %s -> %ss", r.nombre, r.intervalo_segundos)

    # Bajas (recursos desactivados/eliminados)
    for job in scheduler.get_jobs():
        if job.id.startswith("recurso:") and job.id not in activos:
            scheduler.remove_job(job.id)
            log.info("Job baja: %s", job.id)


def registrar_tareas_internas(scheduler: BackgroundScheduler, db: Database, settings: Settings) -> None:
    # Resincronización de jobs con la BD.
    scheduler.add_job(
        sincronizar_jobs,
        trigger=IntervalTrigger(seconds=settings.sync_interval_seg),
        args=[scheduler, db, settings],
        id="sync-jobs",
        replace_existing=True,
    )

    # Reintento de notificaciones fallidas.
    if settings.notif_enabled:
        scheduler.add_job(
            reintentar_pendientes,
            trigger=IntervalTrigger(seconds=settings.notif_retry_interval_seg),
            args=[db, settings],
            id="notif-retry",
            replace_existing=True,
        )

    if not settings.tareas_mantenimiento:
        return

    # Rollup horario (al minuto 5 de cada hora) y diario (00:15).
    scheduler.add_job(repo.rollup_horario, CronTrigger(minute=5), args=[db],
                      id="rollup-horario", replace_existing=True)
    scheduler.add_job(repo.rollup_diario, CronTrigger(hour=0, minute=15), args=[db],
                      id="rollup-diario", replace_existing=True)
    # Purga según retención (03:30).
    scheduler.add_job(repo.purgar_datos, CronTrigger(hour=3, minute=30), args=[db],
                      id="purga", replace_existing=True)
    # Asegurar partición del mes siguiente (día 25 de cada mes).
    scheduler.add_job(_asegurar_particion_proximo_mes, CronTrigger(day=25, hour=1), args=[db],
                      id="particion-mes", replace_existing=True)
    log.info("Tareas de mantenimiento de datos registradas (rollup/purga/particiones).")


def _asegurar_particion_proximo_mes(db: Database) -> None:
    from datetime import date, timedelta
    hoy = date.today()
    repo.asegurar_particiones(db, [hoy, hoy + timedelta(days=31)])
