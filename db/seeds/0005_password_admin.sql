-- =====================================================================
-- 0005_password_admin.sql  (OPCIONAL — auth local)
-- Fija la contraseña del usuario admin del seed usando pgcrypto bcrypt.
-- Requiere la variable psql :admin_pass.
--   psql ... -v admin_pass="<contraseña>" -f 0005_password_admin.sql
-- =====================================================================
BEGIN;

UPDATE perfiles
SET password_hash = crypt(:'admin_pass', gen_salt('bf'))
WHERE email = 'admin@entidad.gov.co';

COMMIT;
