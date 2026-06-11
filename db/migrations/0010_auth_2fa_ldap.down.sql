-- =====================================================================
-- 0010_auth_2fa_ldap.down.sql — Reversa de 0010_auth_2fa_ldap.up.sql
-- =====================================================================
BEGIN;
ALTER TABLE perfiles DROP COLUMN IF EXISTS origen;
ALTER TABLE perfiles DROP COLUMN IF EXISTS totp_activo;
ALTER TABLE perfiles DROP COLUMN IF EXISTS totp_secret;
COMMIT;
