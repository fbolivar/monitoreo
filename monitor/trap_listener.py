"""Receptor de SNMP traps (servicio independiente: simon-traps).

Escucha traps v1/v2c en UDP/162, los clasifica, los asocia a un recurso por IP
de origen y los persiste en la tabla `traps`. Complementa el sondeo periódico
con eventos en TIEMPO REAL (link down/up, cold/warm start, fallas, etc.).

Solo lectura/inserción; no toca el state-machine de incidencias del worker.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

from monitor import repository as repo
from monitor.config import cargar_settings
from monitor.db import Database
from monitor.notificaciones import notificar

SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"
IF_INDEX_PREFIX = "1.3.6.1.2.1.2.2.1.1."  # ifIndex en los varbinds de linkDown/linkUp
LINKDOWN_OID = "1.3.6.1.6.3.1.1.5.3"
LINKUP_OID = "1.3.6.1.6.3.1.1.5.4"

# OID del trap estándar -> (nombre, severidad, descripción)
TRAPS_CONOCIDOS: dict[str, tuple[str, str, str]] = {
    "1.3.6.1.6.3.1.1.5.1": ("coldStart", "info", "Reinicio en frío del equipo"),
    "1.3.6.1.6.3.1.1.5.2": ("warmStart", "info", "Reinicio en caliente del equipo"),
    "1.3.6.1.6.3.1.1.5.3": ("linkDown", "warning", "Interfaz caída (linkDown)"),
    "1.3.6.1.6.3.1.1.5.4": ("linkUp", "info", "Interfaz recuperada (linkUp)"),
    "1.3.6.1.6.3.1.1.5.5": ("authenticationFailure", "warning", "Fallo de autenticación SNMP"),
}

log = logging.getLogger("monitor.traps")


def _procesar(db: Database, settings, source_ip: str | None, var_binds) -> None:
    varbinds: dict[str, str] = {}
    trap_oid = None
    if_index = None
    for oid, val in var_binds:
        soid = str(oid)
        sval = val.prettyPrint()
        varbinds[soid] = sval
        if soid == SNMP_TRAP_OID:
            trap_oid = sval
        elif soid.startswith(IF_INDEX_PREFIX):  # ifIndex de linkDown/linkUp
            try:
                if_index = int(sval)
            except (TypeError, ValueError):
                pass

    nombre, severidad, descr = TRAPS_CONOCIDOS.get(trap_oid or "", (None, "info", None))
    if nombre is None:
        nombre = trap_oid or "trap"
        descr = f"Trap {trap_oid}" if trap_oid else "Trap SNMP"

    recurso_id = repo.recurso_id_por_host(db, source_ip) if source_ip else None
    repo.guardar_trap(db, source_ip, recurso_id, trap_oid, nombre, severidad, descr, varbinds)
    log.info("Trap %s de %s (recurso=%s, if=%s)", nombre, source_ip, recurso_id, if_index)

    # Tiempo real: linkDown/linkUp abren/cierran incidencia de interfaz + notifican.
    if recurso_id and if_index is not None and trap_oid in (LINKDOWN_OID, LINKUP_OID):
        _incidencia_por_trap(db, settings, recurso_id, if_index, trap_oid)


def _incidencia_por_trap(db: Database, settings, recurso_id: int, if_index: int, trap_oid: str) -> None:
    recurso = repo.cargar_recurso(db, recurso_id)
    if recurso is None:
        return
    nombre_if = repo.nombre_interfaz(db, recurso_id, if_index) or f"if{if_index}"
    ahora = datetime.now(timezone.utc)

    if trap_oid == LINKDOWN_OID:
        titulo = f"{recurso.nombre}: puerto {nombre_if} caído (trap)"
        nueva = repo.abrir_incidencia_interfaz(
            db, recurso_id, if_index, nombre_if, "warning", titulo,
            "Trap linkDown recibido en tiempo real.", ahora)
        if nueva:
            log.warning("Incidencia interfaz %s ABIERTA por trap linkDown (recurso %s, %s)",
                        nueva, recurso_id, nombre_if)
            notificar(db, settings, incidencia_id=nueva, recurso=recurso,
                      severidad="warning", evento="apertura", titulo=titulo)
    else:  # linkUp
        ab = repo.incidencia_interfaz_abierta(db, recurso_id, if_index)
        if ab:
            repo.cerrar_incidencia(db, ab["id"], ahora)
            log.info("Incidencia interfaz %s resuelta por trap linkUp (%s).", ab["id"], nombre_if)
            notificar(db, settings, incidencia_id=ab["id"], recurso=recurso,
                      severidad=ab.get("severidad", "warning"), evento="cierre",
                      titulo=f"{recurso.nombre}: puerto {nombre_if} recuperado (trap)")


def main() -> int:
    settings = cargar_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    if not settings.traps_enabled:
        log.info("TRAPS_ENABLED=false; receptor desactivado.")
        return 0

    db = Database(settings)
    try:
        db.ping()
    except Exception:
        log.exception("No se pudo conectar a PostgreSQL. Abortando receptor de traps.")
        return 1

    snmp_engine = engine.SnmpEngine()
    config.addTransport(
        snmp_engine, udp.domainName,
        udp.UdpTransport().openServerMode((settings.trap_bind, settings.trap_port)),
    )
    config.addV1System(snmp_engine, "simon-area", settings.trap_community)

    # La IP de origen se captura con un observer del mensaje entrante.
    estado: dict[str, object] = {"addr": None}

    def _obs(_engine, _execpoint, variables, _cbctx):
        estado["addr"] = variables.get("transportAddress")

    snmp_engine.observer.registerObserver(_obs, "rfc3412.receiveMessage:request")

    def _cb(_engine, _state_ref, _ctx_engine_id, _ctx_name, var_binds, _cbctx):
        try:
            addr = estado.get("addr")
            ip = str(addr[0]) if addr else None
            _procesar(db, settings, ip, var_binds)
        except Exception:
            log.exception("Error procesando trap recibido")

    ntfrcv.NotificationReceiver(snmp_engine, _cb)
    snmp_engine.transportDispatcher.jobStarted(1)
    log.info("Receptor de traps escuchando en %s:%s (community '%s').",
             settings.trap_bind, settings.trap_port, settings.trap_community)
    try:
        snmp_engine.transportDispatcher.runDispatcher()
    except KeyboardInterrupt:
        pass
    finally:
        snmp_engine.transportDispatcher.closeDispatcher()
        db.close()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
