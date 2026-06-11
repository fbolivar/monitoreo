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

        for canal in canales:
            min_sev = (canal.config or {}).get("min_severidad", "info")
            if not severidad_alcanza(min_sev, severidad):
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
            else:
                log.warning("Notif %s -> canal %s (%s) FALLó: %s", evento, canal.nombre, canal.tipo, error)
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
