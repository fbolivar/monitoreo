-- =====================================================================
-- 0001_init.down.sql  — Reversa de 0001_init.up.sql
-- Orden inverso de dependencias. Idempotente (IF EXISTS).
-- =====================================================================
BEGIN;

DROP TABLE IF EXISTS notificaciones;
DROP TABLE IF EXISTS canales_notificacion;
DROP TABLE IF EXISTS mantenimientos;
DROP TABLE IF EXISTS incidencias;
DROP TABLE IF EXISTS umbrales;
DROP TABLE IF EXISTS chequeos;
DROP TABLE IF EXISTS recursos;
DROP TABLE IF EXISTS perfiles;
DROP TABLE IF EXISTS sitios;
DROP TABLE IF EXISTS tipos_recurso;

DROP FUNCTION IF EXISTS descifrar_secreto(bytea, text);
DROP FUNCTION IF EXISTS cifrar_secreto(jsonb, text);
DROP FUNCTION IF EXISTS set_updated_at();

-- pgcrypto se deja instalada (la pueden usar otras migraciones). Descomentar
-- si se quiere reversa total:
-- DROP EXTENSION IF EXISTS pgcrypto;

COMMIT;
