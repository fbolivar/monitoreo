-- =====================================================================
-- 0020_hardware.down.sql — Reversa de 0020_hardware.up.sql
-- =====================================================================
BEGIN;
DROP TABLE IF EXISTS hardware_componentes;
DROP TABLE IF EXISTS hardware_inventario;
COMMIT;
