-- =====================================================================
-- 0018_servicios.down.sql — Reversa de 0018_servicios.up.sql
-- =====================================================================
BEGIN;
DROP TABLE IF EXISTS servicio_componentes;
DROP TABLE IF EXISTS servicios;
COMMIT;
