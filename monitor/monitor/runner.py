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
    # 4c. Anomalías por línea base estacional (opt-in; degrada si una métrica
    #     se dispara fuera de su banda normal de esta hora).
    ev = _detectar_anomalias(db, settings, recurso, resultado, ev, ahora)
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


def _detectar_anomalias(db: Database, settings: Settings, recurso: Recurso,
                        resultado: ResultadoProbe, ev: Evaluacion, ahora: datetime) -> Evaluacion:
    """Si el recurso opta por baseline (parametros.baseline_metricas) y una métrica
    medida supera su banda normal (media + max(k·σ, piso)) de esta hora, degrada.

    Solo aplica sobre estados up/degraded (no down/unknown). Aporta severidad
    'warning' como mucho; la confirmación SOFT/HARD evita alertar por un pico."""
    if not settings.baseline_enabled or ev.estado not in ("up", "degraded"):
        return ev
    opt = (recurso.parametros or {}).get("baseline_metricas")
    if not opt or not isinstance(opt, (list, tuple)):
        return ev

    base = repo.cargar_baselines_hora(db, recurso.id, ahora.hour)
    if not base:
        return ev

    from . import baseline as bl
    medidas = {m.nombre: m.valor for m in resultado.metricas}
    motivos = list(ev.motivos)
    hubo = False
    for metrica in opt:
        if metrica not in medidas or metrica not in base:
            continue
        media, desviacion, muestras = base[metrica]
        if muestras < settings.baseline_min_muestras:   # franja sin historia suficiente
            continue
        a = bl.evaluar_anomalia(metrica, medidas[metrica], media, desviacion,
                                settings.baseline_k, settings.baseline_min_desviacion)
        if a:
            hubo = True
            z = f", z={a.z:.1f}σ" if a.z is not None else ""
            motivos.append(f"anomalía {a.metrica}={a.valor:.1f} > base {a.media:.1f}+{a.banda:.1f}"
                           f"{z} (hora {ahora.hour}h UTC)")

    if not hubo:
        return ev
    severidad = ev.severidad if ev.severidad in ("warning", "critical") else "warning"
    return Evaluacion("degraded", severidad, motivos)


def recalcular_baselines(db: Database, settings: Settings) -> None:
    """Job periódico: recalcula la línea base estacional desde el rollup horario."""
    if not settings.baseline_enabled:
        return
    n = repo.recalcular_baselines(db, settings.baseline_ventana_dias)
    log.info("Líneas base recalculadas: %s franjas (recurso·métrica·hora).", n)


def respaldar_configuraciones(db: Database, settings: Settings) -> None:
    """Respalda la configuración de firewalls (API) y switches (SSH); guarda
    una versión nueva solo si la config cambió (hash) y avisa del cambio."""
    from .probes import fortigate_client

    # Firewalls FortiGate (API REST).
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
            log.warning("Respaldo: no se pudo obtener la config de %s (API)", recurso.nombre)
            continue
        _guardar_respaldo_si_cambio(db, settings, recurso, contenido)

    # Switches y demás equipos por SSH (opt-in parametros.backup.metodo='ssh').
    for recurso in repo.recursos_backup_ssh(db):
        contenido = _respaldo_ssh(db, settings, recurso)
        if contenido is not None:
            _guardar_respaldo_si_cambio(db, settings, recurso, contenido)


def _respaldo_ssh(db: Database, settings: Settings, recurso: Recurso) -> str | None:
    """Obtiene la config de un equipo por SSH. None si falla o falta credencial."""
    from .probes import ssh_config

    host = (recurso.hostname or "").split(":", 1)[0].strip()
    if not host:
        return None
    secretos = (repo.descifrar_secretos(db, recurso.id, settings.app_crypto_key)
                if settings.app_crypto_key else None) or {}
    user = secretos.get("ssh_user")
    password = secretos.get("ssh_password")
    key_pem = secretos.get("ssh_key")
    if not user or (not password and not key_pem):
        log.info("Respaldo SSH: %s sin credenciales (ssh_user/ssh_password|ssh_key).", recurso.nombre)
        return None

    params = recurso.parametros or {}
    puerto = int((params.get("backup") or {}).get("puerto", 22))
    comando = ssh_config.comando_backup(params, recurso.tipo_codigo)
    sin_pag = ssh_config.comando_sin_paginacion(params)
    try:
        crudo = ssh_config.obtener_config(host, puerto, user, password, key_pem,
                                          comando, sin_pag, timeout=45)
    except Exception as e:  # noqa: BLE001
        log.warning("Respaldo SSH: no se pudo obtener la config de %s: %s", recurso.nombre, e)
        return None
    limpio = ssh_config.limpiar_salida(crudo, comando)
    if len(limpio) < 40:  # respuesta vacía / login sin shell / comando inválido
        log.warning("Respaldo SSH: salida demasiado corta de %s (%d bytes); se ignora.",
                    recurso.nombre, len(limpio))
        return None
    return limpio


def _guardar_respaldo_si_cambio(db: Database, settings: Settings, recurso: Recurso,
                                contenido: str) -> None:
    import difflib
    import hashlib

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


def pronosticar_capacidad(db: Database, settings: Settings) -> None:
    """Forecasting de capacidad: regresión sobre el rollup diario de métricas %
    (disco/mem) -> días hasta el techo. Guarda el pronóstico y avisa (sin
    incidencia) cuando cruza por debajo del umbral de días."""
    if not settings.forecast_enabled:
        return
    from . import forecast

    series = repo.series_capacidad(db, settings.forecast_ventana_dias)
    for (rid, nombre, metrica, _unidad), valores in series.items():
        if len(valores) < settings.forecast_min_dias:
            continue
        p = forecast.proyectar(valores, techo=100.0)

        # Solo confiamos en dias_restantes si el ajuste tiene señal suficiente.
        dias = p.dias_restantes
        if dias is not None and (p.r2 is None or p.r2 < settings.forecast_min_r2):
            dias = None

        previo = repo.pronostico_dias_previo(db, rid, metrica)
        repo.guardar_pronostico(db, rid, metrica, p.valor_actual, p.pendiente_dia,
                                dias, 100.0, p.r2, len(valores))

        # Aviso por cruce: solo al pasar de "lejos" a "<= umbral" (evita repetir).
        if dias is not None and 0 <= dias <= settings.forecast_alert_dias:
            if previo is None or previo > settings.forecast_alert_dias:
                log.warning("Pronóstico capacidad: %s · %s llega a %.0f%% en ~%.0f días",
                            nombre, metrica, 100.0, dias)
                notificar_simple(
                    db, settings,
                    f"Capacidad: {nombre} · {metrica} se llena en ~{round(dias)} días",
                    f"La métrica '{metrica}' de {nombre} está en {p.valor_actual:.1f}% y, al ritmo "
                    f"actual (+{p.pendiente_dia:.2f} %/día), alcanzaría el 100% en ~{round(dias)} días. "
                    f"Revisa capacidad/limpieza antes de que se agote.", "warning")


def enviar_reportes_programados(db: Database, settings: Settings) -> None:
    """Job diario: envía por correo los reportes de disponibilidad cuya periodicidad
    toca (diario/semanal/mensual), generando PDF (o CSV) y adjuntándolo."""
    if not settings.reporte_enabled:
        return
    from . import reportes as rep
    from .notificaciones import senders

    ahora = datetime.now(timezone.utc)
    programados = repo.reportes_activos(db)
    if not programados:
        return

    canales = repo.canales_activos(db, settings.app_crypto_key) if settings.app_crypto_key else []
    email = next((c for c in canales if c.tipo == "email"), None)
    if email is None:
        log.warning("Reportes programados: no hay canal email activo; no se pueden enviar.")
        return

    for r in programados:
        if not rep.reporte_due(r["periodo"], r["ultimo_envio_at"], ahora):
            continue
        destinatarios = [d.strip() for d in (r["destinatarios"] or "").split(",") if d.strip()]
        if not destinatarios:
            continue

        filas = repo.disponibilidad(db, rep.rango_segundos(r["rango"]))
        resumen = rep.kpis(filas)
        periodo_txt = rep.RANGO_ETIQUETA.get(r["rango"], r["rango"])
        generado = ahora.strftime("%Y-%m-%d %H:%M UTC")
        titulo = f"Reporte de disponibilidad — {r['nombre']}"

        datos = rep.generar_pdf(filas, titulo, periodo_txt, generado, resumen) if r["formato"] == "pdf" else None
        if datos is not None:
            nombre, subtype = f"disponibilidad_{r['rango']}.pdf", "pdf"
        else:  # CSV (elegido, o fallback si fpdf2 no está)
            datos, nombre, subtype = rep.generar_csv(filas), f"disponibilidad_{r['rango']}.csv", "csv"

        prom = resumen["disponibilidad_promedio"]
        cuerpo = (
            f"{titulo}\n\nPeriodo: {periodo_txt}\nGenerado: {generado}\n\n"
            f"Recursos: {resumen['recursos']}\n"
            f"Disponibilidad promedio: {('%.3f%%' % prom) if prom is not None else 'sin datos'}\n"
            f"Incidencias en el periodo: {resumen['incidencias']}\n\n"
            f"Se adjunta el detalle por recurso ({nombre}).\n\n"
            f"SIMON — Sistema Integral de Monitoreo"
        )
        ok, err, destino = senders.enviar_email_adjunto(
            email, destinatarios, f"[SIMON] {titulo} ({periodo_txt})", cuerpo, nombre, datos, subtype)
        if ok:
            repo.marcar_reporte_enviado(db, r["id"], ahora)
            log.info("Reporte '%s' enviado a %s (%s).", r["nombre"], destino, nombre)
        else:
            log.warning("Reporte '%s' falló al enviar a %s: %s", r["nombre"], destino, err)


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


def recolectar_topologia(db: Database, settings: Settings) -> None:
    """Camina la LLDP-MIB de cada switch (SNMP) y guarda sus vecinos -> topología L2."""
    if not settings.topologia_enabled:
        return
    from .probes import lldp
    from .probes.snmp import construir_credenciales
    from .probes.snmp_client import snmp_walk

    timeout = settings.probe_timeout_ms / 1000
    switches = repo.recursos_switches(db)

    # 1ª pasada: chassis-id (MAC) propio de cada switch -> recurso, para enlazar
    # vecinos por MAC cuando el sysName/IP de gestión no coincide.
    mac_a_recurso: dict[str, int] = {}
    for recurso in switches:
        host = (recurso.hostname or "").split(":", 1)[0].strip()
        if not host:
            continue
        params = recurso.parametros or {}
        secretos = (repo.descifrar_secretos(db, recurso.id, settings.app_crypto_key)
                    if settings.app_crypto_key else None)
        cred = construir_credenciales(params, secretos)
        if cred is None:
            continue
        try:
            res = snmp_walk(host, int(params.get("snmp_port", 161)), cred, lldp.LOC_CHASSIS, timeout, 1)[0]
        except Exception:  # noqa: BLE001
            res = []
        for _oid, val in res:
            mac = lldp.fmt_chassis(val)
            if mac:
                mac_a_recurso[mac] = recurso.id
                break

    # 2ª pasada: vecinos por switch.
    for recurso in switches:
        host = (recurso.hostname or "").split(":", 1)[0].strip()
        if not host:
            continue
        params = recurso.parametros or {}
        secretos = (repo.descifrar_secretos(db, recurso.id, settings.app_crypto_key)
                    if settings.app_crypto_key else None)
        cred = construir_credenciales(params, secretos)
        if cred is None:
            continue
        puerto = int(params.get("snmp_port", 161))
        try:
            walks = {
                "sysname": snmp_walk(host, puerto, cred, lldp.REM_SYSNAME, timeout, 1)[0],
                "portid": snmp_walk(host, puerto, cred, lldp.REM_PORTID, timeout, 1)[0],
                "portdesc": snmp_walk(host, puerto, cred, lldp.REM_PORTDESC, timeout, 1)[0],
                "chassis": snmp_walk(host, puerto, cred, lldp.REM_CHASSIS, timeout, 1)[0],
                "sysdesc": snmp_walk(host, puerto, cred, lldp.REM_SYSDESC, timeout, 1)[0],
            }
            loc_id = snmp_walk(host, puerto, cred, lldp.LOC_PORTID, timeout, 1)[0]
            loc_desc = snmp_walk(host, puerto, cred, lldp.LOC_PORTDESC, timeout, 1)[0]
            manaddr = snmp_walk(host, puerto, cred, lldp.MAN_BASE, timeout, 1)[0]
        except Exception as e:  # noqa: BLE001
            log.warning("LLDP: no se pudo caminar %s (%s): %s", recurso.id, recurso.nombre, e)
            continue

        locales = lldp.parse_puertos_locales(loc_id, loc_desc)
        direcciones = lldp.parse_direcciones_gestion(manaddr)
        vecinos = lldp.parse_vecinos(walks, locales, direcciones)
        # Enlace por MAC (no se enlaza un switch consigo mismo).
        for v in vecinos:
            rid = mac_a_recurso.get(v.get("remote_chassis"))
            v["recurso_remoto_id"] = rid if rid and rid != recurso.id else None
        repo.guardar_vecinos_lldp(db, recurso.id, vecinos)
        log.info("LLDP %s (%s): %d vecino(s).", recurso.id, recurso.nombre, len(vecinos))


def medir_calidad_wan(db: Database, settings: Settings) -> None:
    """Mide la calidad activa de los enlaces WAN/Starlink opt-in (parametros.wan_calidad):
    latencia/jitter/pérdida (ICMP) + throughput (iperf3 si hay servidor) -> MOS."""
    if not settings.wan_calidad_enabled:
        return
    from . import wan_calidad as wc

    filtro = settings.sitios_filtro()
    recursos = repo.recursos_wan_calidad(db)
    if filtro:
        recursos = [r for r in recursos if r.sitio_id in filtro]

    ahora = datetime.now(timezone.utc)
    for recurso in recursos:
        host = (recurso.hostname or "").split(":", 1)[0].strip()
        if not host:
            continue
        if repo.en_mantenimiento(db, recurso, ahora):
            continue
        cfg = recurso.parametros.get("wan_calidad") if recurso.parametros else None
        cfg = cfg if isinstance(cfg, dict) else {}
        try:
            datos = wc.medir(
                host, settings,
                iperf_host=cfg.get("iperf_host"),
                iperf_port=int(cfg.get("iperf_port", 5201)),
                iperf_seg=int(cfg.get("iperf_seg", 5)),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Calidad WAN %s (%s): %s", recurso.id, recurso.nombre, e)
            continue
        repo.guardar_wan_calidad(db, recurso.id, datos)
        # Emite también como métricas para que se grafiquen e historicen solas.
        muestras = [("wan_latency", datos["latency_ms"], "ms"),
                    ("wan_jitter", datos["jitter_ms"], "ms"),
                    ("wan_loss", datos["loss_pct"], "%"),
                    ("wan_mos", datos["mos"], "")]
        if datos["down_mbps"] is not None:
            muestras.append(("wan_down", datos["down_mbps"], "Mbps"))
        if datos["up_mbps"] is not None:
            muestras.append(("wan_up", datos["up_mbps"], "Mbps"))
        repo.guardar_metricas(db, recurso.id,
                              [(n, v, u) for n, v, u in muestras if v is not None], ahora)
        log.info("Calidad WAN %s (%s): MOS %s (%s).",
                 recurso.id, recurso.nombre, datos["mos"], datos["calidad"])


def procesar_hardware(db: Database, settings: Settings) -> None:
    """Sondea el hardware físico (Redfish/IPMI) de los recursos opt-in y persiste
    el snapshot de componentes + inventario. Avisa cuando un componente se degrada."""
    if not settings.hardware_enabled:
        return
    from . import hardware

    ahora = datetime.now(timezone.utc)
    for recurso in repo.recursos_hardware(db):
        try:
            secretos = None
            if settings.app_crypto_key:
                secretos = repo.descifrar_secretos(db, recurso.id, settings.app_crypto_key)

            inventario, comps = hardware.recolectar(recurso, secretos, settings)
            repo.guardar_hardware_inventario(db, recurso.id, inventario)
            repo.guardar_hardware_componentes(db, recurso.id, comps)

            # Incidencias formales por componente (salvo en mantenimiento).
            if not repo.en_mantenimiento(db, recurso, ahora):
                _gestionar_incidencias_hardware(db, settings, recurso, comps, ahora)
            log.info("Hardware %s (%s) -> %s (%d componentes, %s)",
                     recurso.id, recurso.nombre, inventario.get("salud_global"),
                     len(comps), inventario.get("protocolo"))
        except Exception as ex:  # noqa: BLE001
            log.warning("Hardware de %s (%s) no disponible: %s", recurso.id, recurso.nombre, ex)


def _gestionar_incidencias_hardware(db: Database, settings: Settings, recurso: Recurso,
                                    comps: list[dict], ahora: datetime) -> None:
    """Abre/cierra/escala una incidencia por cada componente físico degradado/caído."""
    sev_por_estado = {"down": "critical", "degraded": "warning"}
    # Componentes en mal estado, por clave estable 'categoria:nombre'.
    malos = {f"{c['categoria']}:{c['nombre']}": c
             for c in comps if c["estado"] in ("down", "degraded")}

    for clave, c in malos.items():
        sev = sev_por_estado[c["estado"]]
        lectura = f" ({c['lectura']}{c.get('unidad') or ''})" if c.get("lectura") is not None else ""
        titulo = f"{recurso.nombre}: {c['nombre']} {c['estado']}{lectura}"
        abierta = repo.incidencia_componente_abierta(db, recurso.id, clave)
        if abierta is None:
            nueva = repo.abrir_incidencia_componente(
                db, recurso.id, clave, sev, titulo, f"Componente {c['categoria']} '{c['nombre']}'"
                f" reporta estado {c['estado']}.", ahora)
            if nueva:
                log.warning("Incidencia hardware %s ABIERTA (recurso %s, %s)", nueva, recurso.id, clave)
                notificar(db, settings, incidencia_id=nueva, recurso=recurso,
                          severidad=sev, evento="apertura", titulo=titulo)
        elif abierta.get("severidad") != sev:
            # Cambio de severidad (degraded<->down): actualiza y notifica si escala.
            anterior = abierta.get("severidad")
            repo.actualizar_severidad_incidencia(db, abierta["id"], sev)
            if SEV_ORDEN.get(sev, 0) > SEV_ORDEN.get(anterior, 0):
                notificar(db, settings, incidencia_id=abierta["id"], recurso=recurso,
                          severidad=sev, evento=f"escalamiento:{sev}",
                          titulo=f"Escalamiento {anterior} -> {sev}: {titulo}")

    # Cierra incidencias de componentes que ya se recuperaron (ya no están en 'malos').
    for ab in repo.incidencias_componente_abiertas(db, recurso.id):
        if ab["componente"] not in malos:
            repo.cerrar_incidencia(db, ab["id"], ahora)
            log.info("Incidencia hardware %s resuelta (%s recuperado).", ab["id"], ab["componente"])
            notificar(db, settings, incidencia_id=ab["id"], recurso=recurso,
                      severidad=ab.get("severidad", "warning"), evento="cierre",
                      titulo=f"{recurso.nombre}: {ab['componente']} recuperado")


def procesar_descubrimientos(db: Database, settings: Settings) -> None:
    """Ejecuta los escaneos de auto-descubrimiento en cola (ping sweep + SNMP)."""
    if not settings.descubrimiento_enabled:
        return
    pendientes = repo.escaneos_pendientes(db, settings.app_crypto_key or "")
    for e in pendientes:
        repo.marcar_escaneo(db, e["id"], "ejecutando")
        try:
            _ejecutar_escaneo(db, settings, e)
        except Exception as ex:  # noqa: BLE001
            log.exception("Descubrimiento %s falló", e["id"])
            repo.marcar_escaneo(db, e["id"], "error", str(ex)[:300])


def _ejecutar_escaneo(db: Database, settings: Settings, e: dict) -> None:
    from icmplib import multiping

    from . import descubrimiento as desc
    from .probes.snmp_client import Credenciales, snmp_get

    ips = desc.expandir_subred(e["subred"], settings.descubrimiento_max_hosts)
    if not ips:
        repo.marcar_escaneo(db, e["id"], "error", "subred inválida o demasiado grande")
        return

    timeout = settings.probe_timeout_ms / 1000
    hosts = multiping(ips, count=2, interval=0.03, timeout=1.0, privileged=settings.icmp_privileged)
    vivos = [(h.address, h.avg_rtt) for h in hosts if h.is_alive]

    community = (e.get("secretos") or {}).get("snmp_community")
    cred = Credenciales(version=str(e["snmp_version"]), community=community) if community else None
    oids = {"sysdescr": "1.3.6.1.2.1.1.1.0", "sysobjectid": "1.3.6.1.2.1.1.2.0", "sysname": "1.3.6.1.2.1.1.5.0"}

    candidatos = 0
    for ip, rtt in vivos:
        sysdescr = sysobjectid = sysname = None
        responde = False
        if cred is not None:
            try:
                _ok, vals, _err = snmp_get(ip, 161, cred, oids, timeout, 1)
                if vals.get("sysobjectid") is not None or vals.get("sysdescr") is not None:
                    responde = True
                    sysdescr = str(vals["sysdescr"]) if vals.get("sysdescr") is not None else None
                    sysobjectid = str(vals["sysobjectid"]) if vals.get("sysobjectid") is not None else None
                    sysname = str(vals["sysname"]) if vals.get("sysname") is not None else None
            except Exception:  # noqa: BLE001
                pass
        tipo = desc.clasificar(sysdescr, sysobjectid)
        existe = repo.recurso_id_por_host(db, ip)
        estado = "existente" if existe else "nuevo"
        repo.guardar_candidato(db, e["id"], ip, sysname, sysdescr, sysobjectid, tipo,
                               responde, int(rtt) if rtt else None, estado, existe)
        candidatos += 1

    repo.completar_escaneo(db, e["id"], len(vivos), candidatos)
    log.info("Descubrimiento %s: %d vivos, %d candidatos en %s", e["id"], len(vivos), candidatos, e["subred"])


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
