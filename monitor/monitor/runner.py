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
from .evaluacion import Evaluacion, confirmar_estado, evaluar
from .models import Recurso, Umbral
from .notificaciones import SEV_ORDEN, notificar, notificar_simple
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

    # 4. Evaluación contra umbrales + triggers compuestos (reglas)
    umbrales = repo.cargar_umbrales(db, recurso)
    reglas = repo.cargar_reglas(db, recurso)
    ev = evaluar(resultado, umbrales, reglas)

    # 4b. Detección de failover de clúster (genérica: si el probe reporta ha_primary)
    ev = _detectar_failover(db, recurso, resultado, ev)
    crudo = ev.estado  # estado de ESTE chequeo (sin confirmar)

    # 5. Mantenimiento
    en_mant = repo.en_mantenimiento(db, recurso, ahora)

    # 5a. Confirmación SOFT/HARD: un estado "malo" no se consolida hasta repetirse
    #     N chequeos. Durante mantenimiento la máquina se congela (alertas silenciadas).
    if en_mant:
        conf = None
        estado_persistido = "maintenance"
        estado_hard = recurso.estado_hard  # para la lógica de incidencias/dependencias
    else:
        max_intentos = recurso.max_check_attempts or settings.max_check_attempts
        conf = confirmar_estado(
            recurso.estado_hard, recurso.estado_candidato, recurso.intentos_estado,
            crudo, max_intentos, settings.recovery_attempts,
        )
        estado_persistido = conf.estado_hard
        estado_hard = conf.estado_hard

    # 5b. Dependencia: ¿un ancestro (enlace/firewall aguas arriba) está caído?
    #     Se evalúa sobre el estado HARD (no por un blip puntual).
    dep_caida = None
    if recurso.depende_de_id and estado_hard in ("down", "degraded", "unknown"):
        dep_caida = repo.ancestro_caido(db, recurso.id)

    # 6. Persistencia. En `chequeos` va el estado CRUDO (verdad histórica); en
    #    `recursos.estado_actual` va el HARD/maintenance (dashboard estable).
    estado_chequeo = "maintenance" if en_mant else crudo
    detalle = dict(resultado.detalle)
    detalle["evaluacion"] = {"estado": ev.estado, "severidad": ev.severidad, "motivos": ev.motivos}
    detalle["mantenimiento"] = en_mant
    if conf is not None:
        detalle["soft"] = {
            "estado_hard": conf.estado_hard,
            "candidato": conf.estado_candidato,
            "intentos": conf.intentos,
            "max": (recurso.max_check_attempts or settings.max_check_attempts),
            "transicion": conf.transicion,
        }
    if dep_caida:
        detalle["dependencia_caida"] = dep_caida

    chequeo_id = repo.guardar_chequeo(db, recurso.id, estado_chequeo,
                                      resultado.latencia_ms, detalle, ahora)
    repo.guardar_metricas(db, recurso.id, resultado.muestras_tuplas(), ahora)
    if resultado.interfaces:
        repo.guardar_interfaces(db, recurso.id, resultado.interfaces)
        repo.guardar_interfaces_historico(db, recurso.id, resultado.interfaces)
    if conf is None:
        repo.actualizar_estado_recurso(db, recurso.id, estado_persistido, ahora)
    else:
        repo.actualizar_estado_recurso(db, recurso.id, estado_persistido, ahora,
                                       conf.estado_hard, conf.estado_candidato, conf.intentos)

    # 7. Incidencias + notificaciones (silenciadas durante mantenimiento). Operan
    #    sobre el estado HARD confirmado, no sobre el crudo.
    if not en_mant:
        ev_hard = _evaluacion_hard(estado_hard, ev)
        _gestionar_incidencia(db, settings, recurso, ev_hard, umbrales, chequeo_id, ahora, dep_caida)
        # Incidencias por interfaz monitoreada (uplinks/WAN). Se suprimen si un
        # ancestro está caído (la causa raíz ya alerta).
        if resultado.interfaces and not dep_caida:
            _gestionar_incidencias_interfaces(db, settings, recurso, ahora)

    return estado_persistido


def _evaluacion_hard(estado_hard: str, ev: Evaluacion) -> Evaluacion:
    """Construye la Evaluación que ven las incidencias usando el estado HARD.

    La severidad se toma de la evaluación cruda cuando coincide con el estado
    confirmado; si no, se usa el default del estado HARD (down->critical)."""
    if estado_hard == "down":
        return Evaluacion("down", "critical", ev.motivos or ["sin respuesta"])
    if estado_hard == "degraded":
        sev = ev.severidad if (ev.estado == "degraded" and ev.severidad) else "warning"
        return Evaluacion("degraded", sev, ev.motivos)
    if estado_hard == "unknown":
        return Evaluacion("unknown", "warning", ev.motivos)
    return Evaluacion("up", None, [])


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


def respaldar_configuraciones(db: Database, settings: Settings) -> None:
    """Respalda la configuración de los firewalls; guarda nueva versión solo si cambió."""
    import difflib
    import hashlib

    from .probes import fortigate_client

    for recurso in repo.recursos_por_tipo(db, "firewall"):
        if not recurso.hostname:
            continue
        secretos = (repo.descifrar_secretos(db, recurso.id, settings.app_crypto_key)
                    if settings.app_crypto_key else None)
        token = (secretos or {}).get("api_key")
        if not token:
            continue
        verify = bool((recurso.parametros or {}).get("verify_ssl", False))
        try:
            contenido = fortigate_client.respaldar_config(recurso.hostname, token, verify, 30)
        except Exception:  # noqa: BLE001
            log.warning("Respaldo: no se pudo obtener la config de %s", recurso.nombre)
            continue

        h = hashlib.sha256(contenido.encode("utf-8", "ignore")).hexdigest()
        prev = repo.ultimo_respaldo(db, recurso.id)
        if prev is None:
            repo.guardar_respaldo(db, recurso.id, h, len(contenido), False, None, contenido)
            log.info("Respaldo inicial de %s (%d bytes).", recurso.nombre, len(contenido))
        elif prev["hash"] != h:
            diff = "\n".join(difflib.unified_diff(
                (prev["contenido"] or "").splitlines(), contenido.splitlines(),
                fromfile="anterior", tofile="actual", lineterm=""))
            repo.guardar_respaldo(db, recurso.id, h, len(contenido), True, diff[:200000], contenido)
            log.warning("CAMBIO de configuración detectado en %s.", recurso.nombre)
            notificar_simple(
                db, settings, f"Cambio de configuración: {recurso.nombre}",
                f"La configuración de {recurso.nombre} cambió. Revisa el diff en SIMON "
                f"(detalle del recurso → Respaldos).", "warning")


def latido_externo(db: Database, settings: Settings) -> None:
    """Dead-man's switch: envía un latido a una URL externa solo si la BD responde.
    Si el worker/servidor cae (o la BD no responde), el latido se detiene y el
    servicio externo (p. ej. healthchecks.io) alerta."""
    if not settings.deadman_url:
        return
    try:
        db.ping()
    except Exception:
        log.warning("Dead-man's switch: la BD no responde; no se envía latido.")
        return
    try:
        import httpx
        httpx.get(settings.deadman_url, timeout=10)
    except Exception:  # noqa: BLE001
        log.debug("Dead-man's switch: no se pudo enviar el latido (¿red?).")


def marcar_obsoletos(db: Database, settings: Settings) -> None:
    """Freshness/stale-data: marca 'unknown' los recursos sin chequeo reciente.

    Cubre el punto ciego en que un job muere o un recurso deja de responder en
    silencio (sin disparar 'down'). No genera incidencia (política de 'unknown')."""
    if not settings.freshness_enabled:
        return
    sitios = settings.sitios_filtro() or None
    obsoletos = repo.marcar_recursos_obsoletos(
        db, settings.freshness_factor, settings.freshness_min_seg, sitios)
    for o in obsoletos:
        log.warning("Freshness: recurso %s (%s) sin datos -> unknown (último: %s)",
                    o["id"], o["nombre"], o["ultimo_chequeo_at"])


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
