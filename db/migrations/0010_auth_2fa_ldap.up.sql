-- =====================================================================
-- 0010_auth_2fa_ldap.up.sql
-- 2FA (TOTP) y origen de cuenta (local | ldap) para SSO con AD/LDAP.
--  - totp_secret: secreto base32 (solo backend; nunca se serializa).
--  - totp_activo: si el usuario completó la activación de 2FA.
--  - origen: 'local' (contraseña en perfiles) | 'ldap' (autentica contra AD).
-- =====================================================================
BEGIN;

ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS totp_secret text;
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS totp_activo boolean NOT NULL DEFAULT false;
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS origen text NOT NULL DEFAULT 'local';

COMMENT ON COLUMN perfiles.totp_secret IS 'Secreto TOTP (base32). Nunca se expone por la API.';
COMMENT ON COLUMN perfiles.origen IS 'local = contraseña local; ldap = autenticación contra AD/LDAP.';

COMMIT;
