-- =====================================================================
-- 0011_app_config.up.sql
-- Ajustes de aplicación editables desde la UI (clave -> valor jsonb).
-- Primer uso: configuración de SSO LDAP/AD (clave 'ldap'). Reemplaza la
-- necesidad de editar api/.env: la BD tiene prioridad sobre las env por defecto.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS app_config (
  clave      text PRIMARY KEY,
  valor      jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE app_config IS 'Ajustes de aplicación editables por UI (no sensibles). Ej: ldap.';

COMMIT;
