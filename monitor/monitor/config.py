"""Configuración del worker, leída de variables de entorno (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(nombre: str, defecto: bool = False) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in ("1", "true", "yes", "on", "si", "sí")


def _int(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, str(defecto)))
    except (TypeError, ValueError):
        return defecto


@dataclass(frozen=True)
class Settings:
    # Base de datos
    db_host: str = os.getenv("DB_HOST", "127.0.0.1")
    db_port: int = _int("DB_PORT", 5432)
    db_name: str = os.getenv("DB_DATABASE", "monitoreo")
    db_user: str = os.getenv("DB_USERNAME", "monitoreo")
    db_password: str = os.getenv("DB_PASSWORD", "monitoreo_dev")
    db_sslmode: str = os.getenv("DB_SSLMODE", "prefer")
    db_pool_max: int = _int("DB_POOL_MAX", 8)

    # Cifrado de secretos (pgcrypto, misma clave que API/infra)
    app_crypto_key: str = os.getenv("APP_CRYPTO_KEY", "")

    # Probes
    probe_timeout_ms: int = _int("PROBE_TIMEOUT_MS", 3000)
    icmp_privileged: bool = _bool("ICMP_PRIVILEGED", True)
    icmp_count: int = _int("ICMP_COUNT", 4)

    # Scheduler
    scheduler_max_workers: int = _int("SCHEDULER_MAX_WORKERS", 20)
    misfire_grace: int = _int("MISFIRE_GRACE", 30)
    sync_interval_seg: int = _int("SYNC_INTERVAL_SEG", 60)

    # Mantenimiento de datos (rollup/purga)
    tareas_mantenimiento: bool = _bool("TAREAS_MANTENIMIENTO", True)

    # Notificaciones (FASE 5)
    notif_enabled: bool = _bool("NOTIF_ENABLED", True)
    # Anti-flapping: no reenviar "apertura" del mismo recurso dentro de esta ventana.
    notif_dedup_cooldown_seg: int = _int("NOTIF_DEDUP_COOLDOWN_SEG", 600)
    notif_max_intentos: int = _int("NOTIF_MAX_INTENTOS", 3)
    notif_retry_interval_seg: int = _int("NOTIF_RETRY_INTERVAL_SEG", 120)
    # Escalado por tiempo (on-call): si una incidencia 'abierta' no se reconoce
    # en estos minutos, se reenvía un evento de escalada. 0 = desactivado.
    escalation_min: int = _int("ESCALATION_MIN", 15)
    escalation_check_seg: int = _int("ESCALATION_CHECK_SEG", 60)

    # Health
    health_enabled: bool = _bool("HEALTH_ENABLED", True)
    health_port: int = _int("HEALTH_PORT", 8090)

    # Receptor de SNMP traps (servicio aparte: trap_listener.py)
    traps_enabled: bool = _bool("TRAPS_ENABLED", True)
    trap_bind: str = os.getenv("TRAP_BIND", "0.0.0.0")
    trap_port: int = _int("TRAP_PORT", 162)
    trap_community: str = os.getenv("TRAP_COMMUNITY", "public")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password} sslmode={self.db_sslmode}"
        )


def cargar_settings() -> Settings:
    return Settings()
