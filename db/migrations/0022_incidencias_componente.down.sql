-- =====================================================================
-- 0022_incidencias_componente.down.sql — Reversa de 0022.
-- =====================================================================
BEGIN;
DROP INDEX IF EXISTS uq_incidencia_abierta;
CREATE UNIQUE INDEX uq_incidencia_abierta
  ON incidencias(recurso_id, COALESCE(if_index, -1))
  WHERE estado <> 'resuelta';
ALTER TABLE incidencias DROP COLUMN IF EXISTS componente;
COMMIT;
