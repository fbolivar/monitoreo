"""Motor de notificaciones: decide a qué canales enviar y registra cada envío.

- Deduplicación:
    * por (incidencia, canal, evento): nunca se reenvía el mismo evento.
    * anti-flapping: una 'apertura' del mismo recurso no se reenvía dentro de
      NOTIF_DEDUP_COOLDOWN_SEG (evita spamear la misma caída si oscila).
- Escalamiento por severidad:
    * cada canal puede fijar `config.min_severidad` (info|warning|critical);
      solo recibe eventos de severidad >= ese mínimo (critical escala a más canales).
    * si una incidencia abierta sube de severidad (p.ej. warning -> critical) se
      emite un evento de escalamiento.
- Respeto de mantenimiento: heredado del runner (durante mantenimiento no se
  abren/cierran incidencias, por lo que el motor no se invoca).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from ..models import Recurso

if TYPE_CHECKING:  # solo para anotaciones; evita arrastrar psycopg en imports puros
    from ..config import Settings
    from ..db import Database

log = logging.getLogger(__name__)

SEV_ORDEN = {"info": 1, "warning": 2, "critical": 3}

_ENCABEZADOS = {
    "apertura": "🔴 Incidencia ABIERTA",
    "cierre": "🟢 Incidencia RESUELTA",
}


def severidad_alcanza(min_severidad: str, severidad: str) -> bool:
    """True si `severidad` es >= al mínimo exigido por el canal."""
    return SEV_ORDEN.get(severidad, 0) >= SEV_ORDEN.get(min_severidad, 1)


def canal_aplica(config: dict | None, severidad: str, tipo_codigo: str | None,
                 sitio_id: int | None, ahora_local: datetime) -> bool:
    """¿Este canal debe recibir este evento? ENRUTAMIENTO (función pura, testeable).

    Sin esto, todos los canales reciben todo y un solo buzón acaba con las alertas
    de toda la entidad. Cada filtro es OPCIONAL (ausente o vacío = no filtra):

      - min_severidad : info|warning|critical
      - tipos         : ["servidor","switch_lan"]  -> solo esos tipos de recurso
      - sitios        : [1, 7]                     -> solo esos sitios
      - horario       : {"dias":[1..7] (1=lunes), "desde":"08:00", "hasta":"18:00"}
                        en hora LOCAL. Si `desde` > `hasta` la ventana cruza la
                        medianoche (p.ej. 22:00-06:00), que es el caso de guardia.

    Así el equipo de servidores recibe servidores, cada territorial lo suyo, y el
    canal de guardia solo fuera de horario.
    """
    cfg = config or {}
    if not severidad_alcanza(cfg.get("min_severidad", "info"), severidad):
        return False

    tipos = cfg.get("tipos") or []
    if tipos and tipo_codigo not in tipos:
        return False

    sitios = cfg.get("sitios") or []
    if sitios and sitio_id not in sitios:
        return False

    horario = cfg.get("horario") or {}
    if horario:
        dias = horario.get("dias") or []
        if dias and ahora_local.isoweekday() not in dias:
            return False
        desde, hasta = horario.get("desde"), horario.get("hasta")
        if desde and hasta:
            ahora_hhmm = ahora_local.strftime("%H:%M")
            dentro = ((desde <= ahora_hhmm < hasta) if desde <= hasta
                      else (ahora_hhmm >= desde or ahora_hhmm < hasta))
            if not dentro:
                return False

    return True


def construir_mensaje(evento: str, recurso: Recurso, severidad: str,
                      titulo: str, descripcion: str | None = None) -> dict:
    if evento.startswith("escalamiento"):
        encab = "🟠 ESCALAMIENTO de severidad"
    elif evento == "escalada_tiempo":
        encab = "⏰ Incidencia SIN RECONOCER (escalada)"
    else:
        encab = _ENCABEZADOS.get(evento, evento)

    asunto = f"[{severidad.upper()}] {encab}: {recurso.nombre}"
    lineas = [
        titulo,
        f"Recurso: {recurso.nombre} ({recurso.hostname or 's/IP'})",
        f"Tipo: {recurso.tipo_codigo}",
        f"Severidad: {severidad}",
    ]
    if descripcion:
        lineas.append(f"Detalle: {descripcion}")
    return {
        "evento": evento,
        "asunto": asunto,
        "texto": "\n".join(lineas),
        "recurso_id": recurso.id,
        "recurso": recurso.nombre,
        "severidad": severidad,
    }


def notificar(db: Database, settings: Settings, *, incidencia_id: int, recurso: Recurso,
              severidad: str, evento: str, titulo: str, descripcion: str | None = None) -> None:
    """Envía el evento por los canales que correspondan y registra cada envío."""
    if not settings.notif_enabled:
        return

    # Silenciar notificaciones por recurso: la incidencia se crea igual (visible en
    # el tablero), solo se omite el ENVÍO. Para enlaces ruidosos (p.ej. los MPLS de
    # sede) que si no inundarían el correo. Flag: parametros.silenciar_notificaciones.
    if (recurso.parametros or {}).get("silenciar_notificaciones"):
        log.info("Notif suprimida (recurso silenciado) %s recurso %s", evento, recurso.id)
        return

    from .. import repository as repo
    from . import senders

    try:
        # Anti-flapping: solo aplica a aperturas.
        if evento == "apertura" and repo.apertura_reciente(
            db, recurso.id, settings.notif_dedup_cooldown_seg
        ):
            log.info("Notif suprimida (anti-flapping) apertura recurso %s", recurso.id)
            return

        canales = repo.canales_activos(db, settings.app_crypto_key)
        if not canales:
            return

        msg = construir_mensaje(evento, recurso, severidad, titulo, descripcion)
        # Hora LOCAL del servidor: el horario de un canal (guardia, jornada) lo
        # define el operador en su hora, no en UTC.
        ahora_local = datetime.now().astimezone()

        for canal in canales:
            # Enrutamiento: cada canal recibe solo lo suyo (tipo/sitio/horario/severidad).
            if not canal_aplica(canal.config, severidad, recurso.tipo_codigo,
                                recurso.sitio_id, ahora_local):
                continue
            if repo.ya_notificado(db, incidencia_id, canal.id, evento):
                continue

            ok, error, destino = senders.enviar(canal, msg)
            repo.registrar_notificacion(
                db, incidencia_id, canal.id,
                "enviada" if ok else "fallida",
                destino, msg, 1, error,
            )
            if ok:
                log.info("Notif %s -> canal %s (%s) OK", evento, canal.nombre, canal.tipo)
                # GLPI: guarda el nº de ticket creado en la incidencia (una vez).
                if canal.tipo == "glpi" and evento == "apertura" and destino:
                    repo.set_ticket_externo(db, incidencia_id, destino)
            else:
                log.warning("Notif %s -> canal %s (%s) FALLó: %s", evento, canal.nombre, canal.tipo, error)

        # Web Push (PWA): notifica a los navegadores suscritos (#11).
        if settings.push_enabled and settings.vapid_private_key:
            senders.enviar_push(repo.push_suscripciones(db), msg, settings)
    except Exception:  # nunca romper el ciclo de chequeo por una notificación
        log.exception("Error notificando %s de incidencia %s", evento, incidencia_id)


def notificar_simple(db: Database, settings: Settings, asunto: str, texto: str,
                     severidad: str = "warning") -> None:
    """Envía un aviso suelto (no ligado a incidencia) a los canales activos.
    Para eventos como cambios de configuración. No se registra en `notificaciones`."""
    if not settings.notif_enabled:
        return
    from .. import repository as repo
    from . import senders

    try:
        canales = repo.canales_activos(db, settings.app_crypto_key)
        msg = {"asunto": asunto, "texto": texto, "severidad": severidad, "evento": "evento"}
        for canal in canales:
            # Aquí NO se enruta por tipo/sitio: este aviso no viene ligado a un recurso
            # (cambios de config, pronósticos…), así que no hay con qué filtrar. Se usa
            # solo la severidad: mejor que llegue de más a tragárselo en silencio.
            min_sev = (canal.config or {}).get("min_severidad", "info")
            if not severidad_alcanza(min_sev, severidad):
                continue
            ok, error, _ = senders.enviar(canal, msg)
            if not ok:
                log.warning("Aviso a canal %s falló: %s", canal.nombre, error)
    except Exception:  # noqa: BLE001
        log.exception("Error enviando aviso simple")


def reintentar_pendientes(db: Database, settings: Settings) -> None:
    """Reintenta los envíos fallidos (intentos < NOTIF_MAX_INTENTOS)."""
    if not settings.notif_enabled:
        return

    from .. import repository as repo
    from . import senders

    filas = repo.notificaciones_para_reintentar(db, settings.notif_max_intentos)
    if not filas:
        return

    cache: dict[int, object] = {}
    for f in filas:
        canal = cache.get(f["canal_id"])
        if canal is None:
            canal = repo.canal_por_id(db, f["canal_id"], settings.app_crypto_key)
            cache[f["canal_id"]] = canal

        intentos = f["intentos"] + 1
        if canal is None:
            repo.marcar_notificacion(db, f["id"], "fallida", "canal inactivo o eliminado", intentos)
            continue

        ok, error, _ = senders.enviar(canal, f["payload"])
        repo.marcar_notificacion(db, f["id"], "enviada" if ok else "fallida", error, intentos)
