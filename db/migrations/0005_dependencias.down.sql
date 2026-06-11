-- =====================================================================
-- 0005_dependencias.down.sql — Reversa de 0005_dependencias.up.sql
-- =====================================================================
BEGIN;
DROP INDEX IF EXISTS idx_recursos_depende_de;
ALTER TABLE recursos DROP COLUMN IF EXISTS depende_de_id;
COMMIT;
