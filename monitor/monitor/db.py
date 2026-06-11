"""Acceso a PostgreSQL mediante un pool de conexiones (psycopg 3)."""
from __future__ import annotations

import logging

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import Settings

log = logging.getLogger(__name__)


class Database:
    """Envuelve un ConnectionPool con autocommit y filas como dict."""

    def __init__(self, settings: Settings):
        # El pool debe poder atender a todos los hilos del scheduler a la vez;
        # si no, los chequeos concurrentes bloquean esperando conexión y pueden
        # caducar (PoolTimeout), perdiéndose el chequeo.
        max_size = max(settings.db_pool_max, settings.scheduler_max_workers)
        self.pool = ConnectionPool(
            conninfo=settings.dsn(),
            min_size=1,
            max_size=max_size,
            timeout=15,  # fallar rápido en vez de bloquear 30s por defecto
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=True,
        )

    def connection(self):
        """Context manager que entrega una conexión del pool."""
        return self.pool.connection()

    def ping(self) -> bool:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            return cur.fetchone()["ok"] == 1

    def close(self) -> None:
        self.pool.close()
