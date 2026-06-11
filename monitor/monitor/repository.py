"""Capa de acceso a datos: todas las consultas SQL del worker.

Importante: la lógica de negocio (evaluación de estado) vive en evaluacion.py;
aquí solo hay lectura/escritura. Los secretos se descifran con la MISMA función
pgcrypto que usa la API (`descifrar_secreto`), pasando la clave maestra.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from .db import Database
from .models import Canal, Recurso, Umbral

log = logging.getLogger(__name__)


# ── Recursos ──────────────────────────────────────────────────────────
_SELECT_RECURSO = """
    SELECT r.id, r.nombre, r.hostname, r.parametros, r.intervalo_segundos,
           r.estado_actual, r.sitio_id, r.depende_de_id, t.codigo AS tipo_codigo,
           t.protocolo_default
    FROM recursos r
    JOIN tipos_recurso t ON t.id = r.tipo_id
"""


def _fila_a_recurso(row: dict[str, Any]) -> Recurso:
    return Recurso(
        id=row["id"],
        nombre=row["nombre"],
        hostname=row["hostname"],
        tipo_codigo=row["tipo_codigo"],
        protocolo_default=row["protocolo_default"],
        parametros=row["parametros"] or {},
        intervalo_segundos=row["intervalo_segundos"],
        estado_actual=row["estado_actual"],
        sitio_id=row["sitio_id"],
        depende_de_id=row.get("depende_de_id"),
    )


def ancestro_caido(db: Database, recurso_id: int) -> str | None:
    """Nombre del ancestro (cadena depende_de_id) que está 'down', si lo hay.

    Sube por la cadena de dependencias del recurso; devuelve el nombre del
    ancestro más cercano caído (para suprimir alertas del hijo). El límite de
    nivel evita bucles si hubiera un ciclo en los datos.
    """
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH RECURSIVE cadena AS (
                SELECT id, depende_de_id, estado_actual, nombre, 1 AS nivel
                FROM recursos
                WHERE id = (SELECT depende_de_id FROM recursos WHERE id = %s)
                UNION ALL
                SELECT r.id, r.depende_de_id, r.estado_actual, r.nombre, c.nivel + 1
                FROM recursos r JOIN cadena c ON r.id = c.depende_de_id
                WHERE c.nivel < 20
            )
            SELECT nombre FROM cadena WHERE estado_actual = 'down' ORDER BY nivel LIMIT 1
            """,
            (recurso_id,),
        )
        row = cur.fetchone()
        return row["nombre"] if row else None


def cargar_recursos_activos(db: Database) -> list[Recurso]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(_SELECT_RECURSO + " WHERE r.activo = true ORDER BY r.id")
        return [_fila_a_recurso(r) for r in cur.fetchall()]


def cargar_recurso(db: Database, recurso_id: int) -> Recurso | None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(_SELECT_RECURSO + " WHERE r.id = %s AND r.activo = true", (recurso_id,))
        row = cur.fetchone()
        return _fila_a_recurso(row) if row else None


def descifrar_secretos(db: Database, recurso_id: int, clave: str) -> dict[str, Any] | None:
    """Descifra los secretos del recurso vía pgcrypto (igual que la API)."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT descifrar_secreto(secretos, %s) AS s FROM recursos WHERE id = %s",
            (clave, recurso_id),
        )
        row = cur.fetchone()
        return row["s"] if row and row["s"] is not None else None


# ── Umbrales ──────────────────────────────────────────────────────────
def cargar_umbrales(db: Database, recurso: Recurso) -> list[Umbral]:
    """Umbrales aplicables: específicos del recurso o por tipo. El específico
    de recurso prevalece sobre el de tipo para la misma métrica."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT metrica, operador, valor_warning, valor_critical,
                   duracion_segundos, recurso_id
            FROM umbrales
            WHERE activo = true
              AND (recurso_id = %s OR tipo_id = (
                    SELECT tipo_id FROM recursos WHERE id = %s))
            ORDER BY (recurso_id IS NOT NULL) DESC
            """,
            (recurso.id, recurso.id),
        )
        vistos: set[str] = set()
        umbrales: list[Umbral] = []
        for r in cur.fetchall():
            if r["metrica"] in vistos:  # ya hay uno específico de recurso
                continue
            vistos.add(r["metrica"])
            umbrales.append(Umbral(
                metrica=r["metrica"],
                operador=r["operador"],
                valor_warning=r["valor_warning"],
                valor_critical=r["valor_critical"],
                duracion_segundos=r["duracion_segundos"],
            ))
        return umbrales


# ── Mantenimientos ────────────────────────────────────────────────────
def en_mantenimiento(db: Database, recurso: Recurso, ahora: datetime) -> bool:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM mantenimientos
                WHERE %s BETWEEN inicio AND fin
                  AND (recurso_id = %s
                       OR sitio_id = %s
                       OR (recurso_id IS NULL AND sitio_id IS NULL))
            ) AS m
            """,
            (ahora, recurso.id, recurso.sitio_id),
        )
        return bool(cur.fetchone()["m"])


# ── Chequeos / métricas ───────────────────────────────────────────────
def guardar_chequeo(db: Database, recurso_id: int, estado: str,
                    latencia_ms: float | None, detalle: dict[str, Any],
                    ts: datetime) -> int:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chequeos (recurso_id, ts, estado, latencia_ms, detalle)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (recurso_id, ts, estado,
             int(latencia_ms) if latencia_ms is not None else None,
             Json(detalle)),
        )
        return cur.fetchone()["id"]


def guardar_metricas(db: Database, recurso_id: int,
                     muestras: list[tuple[str, float, str | None]],
                     ts: datetime) -> None:
    if not muestras:
        return
    with db.connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO metricas (recurso_id, metrica, valor, unidad, ts)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (recurso_id, metrica, ts) DO NOTHING
            """,
            [(recurso_id, nombre, valor, unidad, ts) for (nombre, valor, unidad) in muestras],
        )


def guardar_interfaces(db: Database, recurso_id: int, interfaces: list[dict]) -> None:
    """Upsert del snapshot de interfaces y borrado de las que ya no aparecen."""
    if not interfaces:
        return
    indices = [i["if_index"] for i in interfaces]
    with db.connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO interfaces (recurso_id, if_index, if_name, admin_estado, oper_estado,
                                    speed_mbps, in_mbps, out_mbps, util_in, util_out, in_err, out_err, ts)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (recurso_id, if_index) DO UPDATE SET
                if_name = EXCLUDED.if_name, admin_estado = EXCLUDED.admin_estado,
                oper_estado = EXCLUDED.oper_estado, speed_mbps = EXCLUDED.speed_mbps,
                in_mbps = EXCLUDED.in_mbps, out_mbps = EXCLUDED.out_mbps,
                util_in = EXCLUDED.util_in, util_out = EXCLUDED.util_out,
                in_err = EXCLUDED.in_err, out_err = EXCLUDED.out_err, ts = now()
            """,
            [(recurso_id, i["if_index"], i["if_name"], i["admin_estado"], i["oper_estado"],
              i["speed_mbps"], i["in_mbps"], i["out_mbps"], i["util_in"], i["util_out"],
              i["in_err"], i["out_err"]) for i in interfaces],
        )
        # Limpia interfaces que dejaron de estar admin-up (ya no se reportan).
        cur.execute(
            "DELETE FROM interfaces WHERE recurso_id = %s AND NOT (if_index = ANY(%s))",
            (recurso_id, indices),
        )


def guardar_interfaces_historico(db: Database, recurso_id: int, interfaces: list[dict]) -> None:
    """Inserta el throughput de las interfaces oper-up (con dato) para histórico/gráficas."""
    filas = [(recurso_id, i["if_index"], i["in_mbps"], i["out_mbps"])
             for i in interfaces
             if i["oper_estado"] == "up" and (i["in_mbps"] is not None or i["out_mbps"] is not None)]
    if not filas:
        return
    with db.connection() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO interfaces_historico (recurso_id, if_index, in_mbps, out_mbps, ts) "
            "VALUES (%s, %s, %s, %s, now())",
            filas,
        )


def interfaces_monitoreadas(db: Database, recurso_id: int) -> list[dict[str, Any]]:
    """Interfaces marcadas para alertar (monitorear=true) con su estado oper actual."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT if_index, if_name, oper_estado FROM interfaces "
            "WHERE recurso_id = %s AND monitorear = true",
            (recurso_id,),
        )
        return cur.fetchall()


def incidencia_interfaz_abierta(db: Database, recurso_id: int, if_index: int) -> dict[str, Any] | None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, severidad FROM incidencias "
            "WHERE recurso_id = %s AND if_index = %s AND estado <> 'resuelta' LIMIT 1",
            (recurso_id, if_index),
        )
        return cur.fetchone()


def abrir_incidencia_interfaz(db: Database, recurso_id: int, if_index: int, if_nombre: str,
                              severidad: str, titulo: str, descripcion: str | None,
                              ahora: datetime) -> int | None:
    """Abre una incidencia de interfaz. El índice único (recurso, if_index) evita duplicados."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO incidencias
                (recurso_id, if_index, if_nombre, estado, severidad, titulo, descripcion, abierta_at)
            VALUES (%s, %s, %s, 'abierta', %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (recurso_id, if_index, if_nombre, severidad, titulo, descripcion, ahora),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def actualizar_estado_recurso(db: Database, recurso_id: int, estado: str, ts: datetime) -> None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE recursos SET estado_actual = %s, ultimo_chequeo_at = %s WHERE id = %s",
            (estado, ts, recurso_id),
        )


# ── Incidencias ───────────────────────────────────────────────────────
def incidencia_abierta(db: Database, recurso_id: int) -> dict[str, Any] | None:
    """Incidencia abierta DEL RECURSO (no las de interfaz, que llevan if_index)."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, severidad, estado FROM incidencias "
            "WHERE recurso_id = %s AND if_index IS NULL AND estado <> 'resuelta' LIMIT 1",
            (recurso_id,),
        )
        return cur.fetchone()


def inicio_racha_no_up(db: Database, recurso_id: int, ahora: datetime) -> datetime:
    """Timestamp del primer chequeo de la racha actual de estados != up/maintenance.

    Sirve para respetar `duracion_segundos` (anti-flapping) antes de abrir
    una incidencia. Si no hay racha previa, devuelve `ahora`.
    """
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT min(ts) AS inicio FROM chequeos
            WHERE recurso_id = %s
              AND ts > COALESCE(
                    (SELECT max(ts) FROM chequeos
                     WHERE recurso_id = %s AND estado IN ('up', 'maintenance')),
                    '-infinity'::timestamptz)
            """,
            (recurso_id, recurso_id),
        )
        row = cur.fetchone()
        return row["inicio"] if row and row["inicio"] is not None else ahora


def ultimo_ha_primary(db: Database, recurso_id: int) -> str | None:
    """Primario del clúster en el último chequeo (para detectar failover)."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT detalle->>'ha_primary' AS p FROM chequeos "
            "WHERE recurso_id = %s AND detalle ? 'ha_primary' "
            "ORDER BY ts DESC LIMIT 1",
            (recurso_id,),
        )
        row = cur.fetchone()
        return row["p"] if row and row["p"] is not None else None


def abrir_incidencia(db: Database, recurso_id: int, severidad: str, titulo: str,
                     descripcion: str | None, chequeo_id: int, ahora: datetime) -> int | None:
    """Abre una incidencia. El índice único parcial garantiza una sola abierta
    por recurso; ante conflicto, no hace nada."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO incidencias
                (recurso_id, estado, severidad, titulo, descripcion,
                 chequeo_apertura_id, abierta_at)
            VALUES (%s, 'abierta', %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (recurso_id, severidad, titulo, descripcion, chequeo_id, ahora),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def actualizar_severidad_incidencia(db: Database, incidencia_id: int, severidad: str) -> None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE incidencias SET severidad = %s WHERE id = %s",
            (severidad, incidencia_id),
        )


def cerrar_incidencia(db: Database, incidencia_id: int, ahora: datetime) -> None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE incidencias SET estado = 'resuelta', resuelta_at = %s WHERE id = %s",
            (ahora, incidencia_id),
        )


# ── Mantenimiento de datos (rollup / purga / particiones) ─────────────
def asegurar_particiones(db: Database, fechas: list) -> None:
    with db.connection() as conn, conn.cursor() as cur:
        for f in fechas:
            cur.execute("SELECT fn_crear_particion_metricas(%s)", (f,))


# ── Notificaciones (FASE 5) ───────────────────────────────────────────
def canales_activos(db: Database, clave: str) -> list[Canal]:
    """Canales activos con sus secretos descifrados (igual que la API)."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, tipo, nombre, config, descifrar_secreto(secretos, %s) AS secretos "
            "FROM canales_notificacion WHERE activo = true",
            (clave,),
        )
        return [
            Canal(id=r["id"], tipo=r["tipo"], nombre=r["nombre"],
                  config=r["config"] or {}, secretos=r["secretos"])
            for r in cur.fetchall()
        ]


def canal_por_id(db: Database, canal_id: int, clave: str) -> Canal | None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, tipo, nombre, config, descifrar_secreto(secretos, %s) AS secretos "
            "FROM canales_notificacion WHERE id = %s AND activo = true",
            (clave, canal_id),
        )
        r = cur.fetchone()
        return Canal(id=r["id"], tipo=r["tipo"], nombre=r["nombre"],
                     config=r["config"] or {}, secretos=r["secretos"]) if r else None


def ya_notificado(db: Database, incidencia_id: int, canal_id: int, evento: str) -> bool:
    """Dedup por (incidencia, canal, evento): evita reenviar el mismo evento."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM notificaciones "
            "WHERE incidencia_id = %s AND canal_id = %s "
            "AND payload->>'evento' = %s AND estado = 'enviada') AS e",
            (incidencia_id, canal_id, evento),
        )
        return bool(cur.fetchone()["e"])


def apertura_reciente(db: Database, recurso_id: int, cooldown_seg: int) -> bool:
    """Anti-flapping: ¿se envió una 'apertura' para este recurso dentro del cooldown?"""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM notificaciones n
                JOIN incidencias i ON i.id = n.incidencia_id
                WHERE i.recurso_id = %s
                  AND n.payload->>'evento' = 'apertura'
                  AND n.estado = 'enviada'
                  AND n.created_at > now() - make_interval(secs => %s)
            ) AS e
            """,
            (recurso_id, cooldown_seg),
        )
        return bool(cur.fetchone()["e"])


def registrar_notificacion(db: Database, incidencia_id: int, canal_id: int, estado: str,
                           destino: str | None, payload: dict, intentos: int,
                           error: str | None) -> int:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notificaciones
                (incidencia_id, canal_id, estado, destino, payload, intentos, error, enviada_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'enviada' THEN now() ELSE NULL END)
            RETURNING id
            """,
            (incidencia_id, canal_id, estado, destino, Json(payload), intentos, error, estado),
        )
        return cur.fetchone()["id"]


def notificaciones_para_reintentar(db: Database, max_intentos: int) -> list[dict]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, incidencia_id, canal_id, destino, payload, intentos "
            "FROM notificaciones WHERE estado = 'fallida' AND intentos < %s "
            "ORDER BY id LIMIT 100",
            (max_intentos,),
        )
        return cur.fetchall()


def marcar_notificacion(db: Database, notif_id: int, estado: str, error: str | None,
                        intentos: int) -> None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE notificaciones SET estado = %s, error = %s, intentos = %s, "
            "enviada_at = CASE WHEN %s = 'enviada' THEN now() ELSE enviada_at END "
            "WHERE id = %s",
            (estado, error, intentos, estado, notif_id),
        )


def rollup_horario(db: Database) -> None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT fn_rollup_metricas_horario()")


def rollup_diario(db: Database) -> None:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT fn_rollup_metricas_diario()")


def purgar_datos(db: Database) -> dict[str, Any]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT fn_purgar_datos() AS r")
        r = cur.fetchone()["r"]
        # Histórico de interfaces: retención corta (7 días).
        cur.execute("DELETE FROM interfaces_historico WHERE ts < now() - interval '7 days'")
        return r
