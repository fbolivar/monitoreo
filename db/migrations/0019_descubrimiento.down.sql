-- =====================================================================
-- 0019_descubrimiento.down.sql — Reversa de 0019_descubrimiento.up.sql
-- =====================================================================
BEGIN;
DROP TABLE IF EXISTS descubrimiento_candidatos;
DROP TABLE IF EXISTS descubrimiento_escaneos;
COMMIT;
