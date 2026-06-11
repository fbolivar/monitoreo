-- =====================================================================
-- 0007_interfaces_fase2.down.sql — Reversa de 0007_interfaces_fase2.up.sql
-- =====================================================================
BEGIN;

DROP INDEX IF EXISTS uq_incidencia_abierta;
CREATE UNIQUE INDEX uq_incidencia_abierta ON incidencias(recurso_id)
  WHERE estado <> 'resuelta';

ALTER TABLE incidencias DROP COLUMN IF EXISTS if_nombre;
ALTER TABLE incidencias DROP COLUMN IF EXISTS if_index;

ALTER TABLE interfaces DROP COLUMN IF EXISTS monitorear;

DROP TABLE IF EXISTS interfaces_historico;

COMMIT;
