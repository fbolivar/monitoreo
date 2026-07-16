-- =====================================================================
-- 0035_reportes_programados_filtro.down.sql
-- =====================================================================
BEGIN;

ALTER TABLE reportes_programados
  DROP COLUMN IF EXISTS tipo_id,
  DROP COLUMN IF EXISTS sitio_id;

COMMIT;
