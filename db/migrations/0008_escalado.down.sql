-- =====================================================================
-- 0008_escalado.down.sql — Reversa de 0008_escalado.up.sql
-- =====================================================================
BEGIN;
ALTER TABLE incidencias DROP COLUMN IF EXISTS escalada_at;
COMMIT;
