"""Receptor de SYSLOG (servicio independiente: simon-syslog).

Escucha mensajes syslog en UDP/514, los parsea (RFC 3164/5424), los asocia a un
recurso por IP de origen y los persiste en `syslog_eventos`. Muchos equipos de red
solo reportan por syslog; esto complementa el sondeo y los SNMP traps.

Opcional (OFF por defecto): un mensaje 'critical' de un recurso mapeado puede
disparar un aviso, con cooldown por recurso para no inundar.
"""
from __future__ import annotations

import asyncio
import logging
import time

from datetime import datetime, timezone

from monitor import repository as repo
from monitor import syslog_reglas as sreglas
from monitor.config import cargar_settings
from monitor.db import Database
from monitor.notificaciones import notificar, notificar_simple
from monitor.syslog_parse import parse_syslog

log = logging.getLogger("monitor.syslog")
_REGLAS_REFRESCO_SEG = 60


class _SyslogProtocol(asyncio.DatagramProtocol):
    def __init__(self, db: Database, settings) -> None:
        self.db = db
        self.settings = settings
        self._ultimo_aviso: dict[int, float] = {}  # recurso_id -> epoch del último aviso
        self._reglas: list[dict] = []
        self._reglas_ts = 0.0

    def _reglas_vigentes(self) -> list[dict]:
        ahora = time.time()
        if ahora - self._reglas_ts >= _REGLAS_REFRESCO_SEG or not self._reglas_ts:
            try:
                self._reglas = sreglas.compilar(repo.cargar_syslog_reglas(self.db))
            except Exception:
                log.exception("No se pudieron cargar las reglas de syslog")
            self._reglas_ts = ahora
        return self._reglas

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            self._procesar(data, addr[0] if addr else None)
        except Exception:  # nunca morir por un datagrama malo
            log.exception("Error procesando datagrama syslog")

    def _procesar(self, data: bytes, ip: str | None) -> None:
        raw = data.decode("utf-8", "replace")
        datos = parse_syslog(raw)
        recurso_id = repo.recurso_id_por_host(self.db, ip) if ip else None
        repo.guardar_syslog(self.db, ip, recurso_id, datos)
        log.debug("syslog %s de %s (recurso=%s): %s",
                  datos["severidad"], ip, recurso_id, (datos.get("mensaje") or "")[:80])

        # Reglas patrón→incidencia (abrir/cerrar), solo si el evento mapeó a un recurso.
        if recurso_id:
            matches = sreglas.evaluar(datos, self._reglas_vigentes())
            for regla in matches:
                self._aplicar_regla(recurso_id, regla, datos)

        if (self.settings.syslog_alert_enabled and recurso_id
                and datos.get("severidad") == "critical"):
            self._avisar(recurso_id, datos)

    def _aplicar_regla(self, recurso_id: int, regla: dict, datos: dict) -> None:
        componente = "syslog:" + str(regla["clave"])
        ahora = datetime.now(timezone.utc)
        recurso = repo.cargar_recurso(self.db, recurso_id)
        if recurso is None:
            return
        try:
            if regla["accion"] == "abrir":
                sev = regla.get("severidad") or "warning"
                titulo = f"{recurso.nombre}: {regla['nombre']}"
                descr = (datos.get("mensaje") or "")[:500]
                nueva = repo.abrir_incidencia_componente(self.db, recurso_id, componente, sev,
                                                         titulo, descr, ahora)
                if nueva:
                    log.warning("Incidencia %s ABIERTA por regla syslog '%s' (recurso %s)",
                                nueva, regla["nombre"], recurso_id)
                    if regla.get("notificar"):
                        notificar(self.db, self.settings, incidencia_id=nueva, recurso=recurso,
                                  severidad=sev, evento="apertura", titulo=titulo)
            else:  # cerrar
                ab = repo.incidencia_componente_abierta(self.db, recurso_id, componente)
                if ab:
                    repo.cerrar_incidencia(self.db, ab["id"], ahora)
                    log.info("Incidencia %s cerrada por regla syslog '%s' (recurso %s)",
                             ab["id"], regla["nombre"], recurso_id)
                    if regla.get("notificar"):
                        notificar(self.db, self.settings, incidencia_id=ab["id"], recurso=recurso,
                                  severidad=ab.get("severidad", "warning"), evento="cierre",
                                  titulo=f"{recurso.nombre}: {regla['nombre']} (resuelto)")
        except Exception:
            log.exception("Error aplicando regla syslog '%s' a recurso %s", regla.get("nombre"), recurso_id)

    def _avisar(self, recurso_id: int, datos: dict) -> None:
        ahora = time.time()
        ultimo = self._ultimo_aviso.get(recurso_id, 0)
        if ahora - ultimo < self.settings.syslog_alert_cooldown_seg:
            return  # cooldown: ya avisamos de este recurso hace poco
        self._ultimo_aviso[recurso_id] = ahora
        recurso = repo.cargar_recurso(self.db, recurso_id)
        nombre = recurso.nombre if recurso else f"recurso {recurso_id}"
        try:
            notificar_simple(
                self.db, self.settings,
                asunto=f"[SYSLOG] {nombre}: evento crítico",
                texto=f"{datos.get('hostname') or ''} {datos.get('app') or ''}: {datos.get('mensaje')}",
                severidad="critical",
            )
        except Exception:
            log.exception("Error avisando por syslog de recurso %s", recurso_id)


def main() -> int:
    settings = cargar_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    if not settings.syslog_enabled:
        log.info("SYSLOG_ENABLED=false; receptor desactivado.")
        return 0

    db = Database(settings)
    try:
        db.ping()
    except Exception:
        log.exception("No se pudo conectar a PostgreSQL. Abortando receptor de syslog.")
        return 1

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    log.info("Receptor de syslog escuchando en %s:%s.", settings.syslog_bind, settings.syslog_port)
    try:
        transport, _ = loop.run_until_complete(loop.create_datagram_endpoint(
            lambda: _SyslogProtocol(db, settings),
            local_addr=(settings.syslog_bind, settings.syslog_port),
        ))
    except Exception:
        log.exception("No se pudo abrir el socket UDP %s:%s", settings.syslog_bind, settings.syslog_port)
        db.close()
        return 1
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        transport.close()
        loop.close()
        db.close()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
