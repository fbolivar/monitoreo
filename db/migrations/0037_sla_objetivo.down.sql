-- =====================================================================
-- 0037_sla_objetivo.down.sql
-- =====================================================================
BEGIN;

ALTER TABLE recursos      DROP COLUMN IF EXISTS sla_objetivo;
ALTER TABLE tipos_recurso DROP COLUMN IF EXISTS sla_objetivo;

COMMIT;
