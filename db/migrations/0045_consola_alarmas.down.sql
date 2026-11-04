-- =====================================================================
-- 0045_consola_alarmas.down.sql
-- =====================================================================
BEGIN;

DROP TABLE IF EXISTS relevos_turno;

ALTER TABLE incidencias
  DROP COLUMN IF EXISTS asignado_a,
  DROP COLUMN IF EXISTS silenciado_hasta;

COMMIT;
