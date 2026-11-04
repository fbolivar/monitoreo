-- =====================================================================
-- 0048_causa_raiz_topologia.down.sql
-- =====================================================================
BEGIN;

ALTER TABLE recursos
  DROP COLUMN IF EXISTS es_nucleo,
  DROP COLUMN IF EXISTS padre_topologia_id;

COMMIT;
