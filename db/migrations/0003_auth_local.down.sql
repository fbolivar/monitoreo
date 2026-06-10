-- =====================================================================
-- 0003_auth_local.down.sql — Reversa de 0003_auth_local.up.sql
-- =====================================================================
BEGIN;

ALTER TABLE perfiles DROP COLUMN IF EXISTS password_hash;

COMMIT;
