-- =====================================================================
-- 0003_auth_local.up.sql
-- Autenticación LOCAL (sin Supabase): contraseña hasheada (bcrypt) en perfiles.
-- La API verifica la contraseña y emite su propio JWT. `password_hash` es
-- compatible con bcrypt de PHP (password_hash/password_verify) y con
-- pgcrypto crypt(..., gen_salt('bf')).
-- =====================================================================
BEGIN;

ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS password_hash text;

COMMENT ON COLUMN perfiles.password_hash IS
  'Hash bcrypt de la contraseña (auth local). NULL = usuario sin contraseña (no puede iniciar sesión).';

COMMIT;
