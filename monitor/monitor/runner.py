"""Orquestación de UN ciclo de chequeo de un recurso.

Flujo:
  1. Cargar recurso (config fresca).
  2. Seleccionar probe (icmp/http/tcp) y descifrar secretos si hace falta.
  3. Ejecutar el probe -> ResultadoProbe (medidas crudas).
  4. Evaluar estado contra umbrales -> Evaluacion (estado + severidad).
  5. ¿En ventana de mantenimiento? -> el estado persistido pasa a 'maintenance'.
  6. Escribir chequeo + métricas + estado_actual del recurso.
  7. Si NO hay mantenimiento: abrir/cerrar incidencia según el estado
     (respetando duracion_segundos de los umbrales para anti-flapping).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import repository as repo
from .config import Settings
from .db import Database
from .evaluacion import Evaluacion, evaluar
from .models import Recurso, Umbral
from .notificaciones import SEV_ORDEN, notificar
from .probes import seleccionar_probe
from .probes.base import ResultadoProbe

log = logging.getLogger(__name__)


def ejecutar_chequeo_por_id(db: Database, settings: Settings, recurso_id: int) -> None:
    """Punto de entrada del job de APScheduler: recarga el recurso y lo chequea."""
    recurso = repo.cargar_recurso(db, recurso_id)
    if recurso is None:
        log.debug("Recurso %s inactivo o inexistente; se omite.", recurso_id)
        return
    try:
        estado = chequear(db, settings, recurso)
        log.info("Chequeo %s (%s) -> %s", recurso.id, recurso.nombre, estado)
    except Exception:  # nunca dejar caer el scheduler por un recurso
        log.exception("Fallo al chequear recurso %s (%s)", recurso.id, recurso.nombre)


def chequear(db: Database, settings: Settings, recurso: Recurso) -> str:
    ahora = datetime.now(timezone.utc)

    # 2-3. Probe + secretos + ejecución
    resultado = _ejecutar_probe(db, settings, recurso)

    # 4. Evaluación contra umbrales
    umbrales = repo.cargar_umbrales(db, recurso)
    ev = evaluar(resultado, umbrales)

    # 4b. Detección de failover de clúster (genérica: si el probe reporta ha_primary)
    ev = _detectar_failover(db, recurso, resultado, ev)

    # 5. Mantenimiento
    en_mant = repo.en_mantenimiento(db, recurso, ahora)
    estado_persistido = "maintenance" if en_mant else ev.estado

    # 5b. Dependencia: ¿un ancestro (enlace/firewall aguas arriba) está caído?
    #     Si es así, la caída de este recurso es consecuencia, no causa raíz.
    dep_caida = None
    if recurso.depende_de_id and ev.estado in ("down", "degraded", "unknown"):
        dep_caida = repo.ancestro_caido(db, recurso.id)

    # 6. Persistencia de chequeo + métricas + estado
    detalle = dict(resultado.detalle)
    detalle["evaluacion"] = {"estado": ev.estado, "severidad": ev.severidad, "motivos": ev.motivos}
    detalle["mantenimiento"] = en_mant
    if dep_caida:
        detalle["dependencia_caida"] = dep_caida

    chequeo_id = repo.guardar_chequeo(db, recurso.id, estado_persistido,
                                      resultado.latencia_ms, detalle, ahora)
    repo.guardar_metricas(db, recurso.id, resultado.muestras_tuplas(), ahora)
    if resultado.interfaces:
        repo.guardar_interfaces(db, recurso.id, resultado.interfaces)
        repo.guardar_interfaces_historico(db, recurso.id, resultado.interfaces)
    repo.actualizar_estado_recurso(db, recurso.id, estado_persistido, ahora)

    # 7. Incidencias + notificaciones (silenciadas durante mantenimiento)
    if not en_mant:
        _gestionar_incidencia(db, settings, recurso, ev, umbrales, chequeo_id, ahora, dep_caida)
        # Incidencias por interfaz monitoreada (uplinks/WAN). Se suprimen si un
        # ancestro está caído (la causa raíz ya alerta).
        if resultado.interfaces and not dep_caida:
            _gestionar_incidencias_interfaces(db, settings, recurso, ahora)

    return estado_persistido


def _ejecutar_probe(db: Database, settings: Settings, recurso: Recurso) -> ResultadoProbe:
    probe = seleccionar_probe(recurso)
    if probe is None:
        return ResultadoProbe(False, "unknown", None, [],
                              {"motivo": "sin método de chequeo (recurso sin host o protocolo no soportado)",
                               "protocolo": recurso.protocolo_default})

    secretos = None
    if probe.requiere_secretos and settings.app_crypto_key:
        secretos = repo.descifrar_secretos(db, recurso.id, settings.app_crypto_key)

    try:
        return probe.run(recurso, secretos, settings)
    except Exception as e:
        log.exception("Probe %s falló para recurso %s", probe.nombre, recurso.id)
        return ResultadoProbe(False, "down", None, [], {"error": str(e), "probe": probe.nombre})


def _detectar_failover(db: Database, recurso: Recurso, resultado: ResultadoProbe,
                       ev: Evaluacion) -> Evaluacion:
    """Si el probe reporta `ha_primary`, compara con el primario del último
    chequeo. Si cambió, marca failover y eleva el estado a degraded (mínimo)."""
    primary = resultado.detalle.get("ha_primary")
    if not primary:
        return ev

    previo = repo.ultimo_ha_primary(db, recurso.id)
    if previo and previo != primary:
        resultado.detalle["ha_failover"] = True
        resultado.detalle["ha_primary_anterior"] = previo
        motivo = f"failover HA: {previo} -> {primary}"
        log.warning("Failover detectado en %s: %s", recurso.nombre, motivo)
        if ev.estado == "up":
            return Evaluacion("degraded", "warning", [motivo])
        ev.motivos.append(motivo)
    return ev


def escalar_incidencias(db: Database, settings: Settings) -> None:
    """Job periódico: escala incidencias 'abierta' no reconocidas a tiempo (on-call)."""
    if not settings.escalation_min or settings.escalation_min <= 0:
        return
    ahora = datetime.now(timezone.utc)
    for row in repo.incidencias_para_escalar(db, settings.escalation_min):
        recurso = Recurso(
            id=row["rid"], nombre=row["nombre"], hostname=row["hostname"],
            tipo_codigo=row["tipo_codigo"], protocolo_default="",
        )
        log.warning("Escalando incidencia %s (sin reconocer > %s min)", row["id"], settings.escalation_min)
        notificar(
            db, settings, incidencia_id=row["id"], recurso=recurso,
            severidad=row["severidad"], evento="escalada_tiempo",
            titulo=f"Sin reconocer hace +{settings.escalation_min} min: {row['titulo']}",
        )
        repo.marcar_escalada(db, row["id"], ahora)


def _gestionar_incidencias_interfaces(db: Database, settings: Settings, recurso: Recurso,
                                      ahora: datetime) -> None:
    """Abre/cierra incidencias por interfaz monitoreada según su estado oper."""
    for itf in repo.interfaces_monitoreadas(db, recurso.id):
        idx, nombre, oper = itf["if_index"], itf["if_name"], itf["oper_estado"]
        if oper == "down":
            titulo = f"{recurso.nombre}: puerto {nombre} caído"
            nueva = repo.abrir_incidencia_interfaz(
                db, recurso.id, idx, nombre, "warning", titulo,
                f"La interfaz monitoreada {nombre} está oper-down.", ahora)
            if nueva:
                log.warning("Incidencia interfaz %s ABIERTA (recurso %s, puerto %s)",
                            nueva, recurso.id, nombre)
                notificar(db, settings, incidencia_id=nueva, recurso=recurso,
                          severidad="warning", evento="apertura", titulo=titulo)
        elif oper == "up":
            ab = repo.incidencia_interfaz_abierta(db, recurso.id, idx)
            if ab:
                repo.cerrar_incidencia(db, ab["id"], ahora)
                log.info("Incidencia interfaz %s resuelta (puerto %s recuperado).", ab["id"], nombre)
                notificar(db, settings, incidencia_id=ab["id"], recurso=recurso,
                          severidad=ab.get("severidad", "warning"), evento="cierre",
                          titulo=f"{recurso.nombre}: puerto {nombre} recuperado")


def _gestionar_incidencia(db: Database, settings: Settings, recurso: Recurso, ev: Evaluacion,
                          umbrales: list[Umbral], chequeo_id: int, ahora: datetime,
                          dep_caida: str | None = None) -> None:
    abierta = repo.incidencia_abierta(db, recurso.id)

    # Recuperación: vuelve a 'up' -> cerrar incidencia abierta + notificar cierre.
    if ev.estado == "up":
        if abierta:
            repo.cerrar_incidencia(db, abierta["id"], ahora)
            log.info("Incidencia %s resuelta (recurso %s recuperado).", abierta["id"], recurso.id)
            notificar(
                db, settings, incidencia_id=abierta["id"], recurso=recurso,
                severidad=abierta.get("severidad", "info"), evento="cierre",
                titulo=f"Recurso {recurso.nombre} recuperado (operativo)",
            )
        return

    # 'unknown': no abrimos incidencia (evita ruido por problemas de sondeo).
    if ev.estado == "unknown":
        return

    # Supresión por dependencia: si un ancestro está down, esta caída es
    # consecuencia (no causa raíz). No abrimos incidencia ni notificamos.
    if dep_caida:
        log.info("Recurso %s %s suprimido: ancestro '%s' caído (sin alerta).",
                 recurso.id, ev.estado, dep_caida)
        return

    # 'degraded' / 'down'
    if abierta is None:
        # Anti-flapping: 'down' dispara inmediato; 'degraded' respeta duracion_segundos.
        if ev.estado == "degraded":
            duracion = max((u.duracion_segundos for u in umbrales), default=0)
            if duracion > 0:
                inicio = repo.inicio_racha_no_up(db, recurso.id, ahora)
                if (ahora - inicio).total_seconds() < duracion:
                    log.debug("Recurso %s degradado pero dentro de gracia (%ss).", recurso.id, duracion)
                    return

        titulo = f"{recurso.nombre}: {ev.estado} ({ev.severidad})"
        descripcion = "; ".join(ev.motivos) or None
        nueva = repo.abrir_incidencia(db, recurso.id, ev.severidad, titulo, descripcion, chequeo_id, ahora)
        if nueva:
            log.warning("Incidencia %s ABIERTA para recurso %s: %s", nueva, recurso.id, titulo)
            notificar(
                db, settings, incidencia_id=nueva, recurso=recurso,
                severidad=ev.severidad, evento="apertura", titulo=titulo, descripcion=descripcion,
            )
    else:
        # Ya hay incidencia abierta: si SUBE de severidad, escalar (y notificar).
        anterior = abierta.get("severidad")
        if anterior != ev.severidad:
            repo.actualizar_severidad_incidencia(db, abierta["id"], ev.severidad)
            if SEV_ORDEN.get(ev.severidad, 0) > SEV_ORDEN.get(anterior, 0):
                notificar(
                    db, settings, incidencia_id=abierta["id"], recurso=recurso,
                    severidad=ev.severidad, evento=f"escalamiento:{ev.severidad}",
                    titulo=f"Escalamiento de severidad: {anterior} -> {ev.severidad}",
                    descripcion="; ".join(ev.motivos) or None,
                )
