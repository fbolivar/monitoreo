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
    # Recolección de interfaces (IF-MIB) DESACOPLADA del chequeo base: el walk de
    # interfaces es el grueso del coste SNMP (cientos de varbinds). La base
    # (cpu/mem/disco) corre cada ciclo; las interfaces solo cada N segundos. Los
    # eventos de enlace en tiempo real los cubren los traps. 0 = en cada chequeo.
    interfaces_intervalo_seg: int = _int("INTERFACES_INTERVALO_SEG", 300)

    # Scheduler. Chequeos I/O-bound -> conviene un pool amplio para que las sondas
    # SNMP lentas no starven a las web (120s) y estas no se descarten por misfire.
    scheduler_max_workers: int = _int("SCHEDULER_MAX_WORKERS", 50)
    misfire_grace: int = _int("MISFIRE_GRACE", 90)
    sync_interval_seg: int = _int("SYNC_INTERVAL_SEG", 60)

    # Estados SOFT/HARD (anti-falsos-positivos). Un estado "malo" se confirma como
    # HARD tras N chequeos consecutivos; solo entonces se abre incidencia/notifica.
    # La recuperación a 'up' suele quererse inmediata (cerrar rápido) -> 1.
    max_check_attempts: int = _int("MAX_CHECK_ATTEMPTS", 3)
    recovery_attempts: int = _int("RECOVERY_ATTEMPTS", 1)

    # Freshness / stale-data: si un recurso lleva más de FRESHNESS_FACTOR×intervalo
    # sin chequeo (job muerto, recurso que dejó de responder en silencio), se marca
    # 'unknown'. FRESHNESS_MIN_SEG es un piso absoluto para intervalos muy cortos.
    freshness_enabled: bool = _bool("FRESHNESS_ENABLED", True)
    freshness_factor: int = _int("FRESHNESS_FACTOR", 3)
    freshness_min_seg: int = _int("FRESHNESS_MIN_SEG", 120)
    freshness_check_seg: int = _int("FRESHNESS_CHECK_SEG", 60)

    # Auto-descubrimiento de red: barrido de subred (ping + SNMP sysDescr/sysObjectID)
    # que propone equipos candidatos. El worker toma los escaneos 'pendiente' en cola.
    descubrimiento_enabled: bool = _bool("DESCUBRIMIENTO_ENABLED", True)
    descubrimiento_check_seg: int = _int("DESCUBRIMIENTO_CHECK_SEG", 15)
    descubrimiento_max_hosts: int = _int("DESCUBRIMIENTO_MAX_HOSTS", 1024)

    # Mantenimiento de datos (rollup/purga)
    tareas_mantenimiento: bool = _bool("TAREAS_MANTENIMIENTO", True)

    # Forecasting de capacidad: regresión sobre rollup diario de métricas % (disco/mem).
    # Avisa (sin incidencia) cuando una métrica llegará al techo en <= FORECAST_ALERT_DIAS.
    forecast_enabled: bool = _bool("FORECAST_ENABLED", True)
    forecast_ventana_dias: int = _int("FORECAST_VENTANA_DIAS", 30)   # historia a considerar
    forecast_min_dias: int = _int("FORECAST_MIN_DIAS", 5)            # mínimo de puntos para fiarse
    forecast_min_r2: float = float(os.getenv("FORECAST_MIN_R2", "0.5"))  # confianza mínima del ajuste
    forecast_alert_dias: int = _int("FORECAST_ALERT_DIAS", 14)       # umbral de aviso

    # Línea base estacional / detección de anomalías (umbral dinámico).
    # Opt-in por recurso (parametros.baseline_metricas). Una métrica que supera
    # media + max(k·σ, piso) de su franja horaria -> degradado (vía SOFT/HARD).
    baseline_enabled: bool = _bool("BASELINE_ENABLED", True)
    baseline_ventana_dias: int = _int("BASELINE_VENTANA_DIAS", 30)   # historia para la línea base
    baseline_min_muestras: int = _int("BASELINE_MIN_MUESTRAS", 7)    # mínimo de días por franja horaria
    baseline_k: float = float(os.getenv("BASELINE_K", "3"))          # nº de desviaciones (3σ ~ 99.7%)
    baseline_min_desviacion: float = float(os.getenv("BASELINE_MIN_DESVIACION", "5"))  # piso absoluto

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

    # Reportes programados (SLA por correo). El worker revisa a diario qué toca
    # enviar según la periodicidad de cada reporte (diario/semanal/mensual).
    reporte_enabled: bool = _bool("REPORTE_PROGRAMADO_ENABLED", True)
    reporte_hora: int = _int("REPORTE_HORA", 6)   # hora (UTC) del chequeo diario

    # Health
    health_enabled: bool = _bool("HEALTH_ENABLED", True)
    health_port: int = _int("HEALTH_PORT", 8090)

    # Receptor de SNMP traps (servicio aparte: trap_listener.py)
    traps_enabled: bool = _bool("TRAPS_ENABLED", True)
    trap_bind: str = os.getenv("TRAP_BIND", "0.0.0.0")
    trap_port: int = _int("TRAP_PORT", 162)
    trap_community: str = os.getenv("TRAP_COMMUNITY", "public")

    # Dead-man's switch: el worker manda un "latido" a esta URL externa cada
    # deadman_interval_seg. Si SIMON (o el servidor) se cae, ese servicio externo
    # deja de recibir el latido y alerta. Vacío = desactivado.
    deadman_url: str = os.getenv("DEADMAN_URL", "")
    deadman_interval_seg: int = _int("DEADMAN_INTERVAL_SEG", 60)

    # Pollers distribuidos: si se define (ej "1,3,5"), este worker SOLO atiende los
    # recursos de esos sitios. Permite desplegar un worker por sede/parque remoto.
    worker_sitios: str = os.getenv("WORKER_SITIOS", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def sitios_filtro(self) -> list[int]:
        return [int(x) for x in self.worker_sitios.split(",") if x.strip().isdigit()]

    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password} sslmode={self.db_sslmode}"
        )


def cargar_settings() -> Settings:
    return Settings()
