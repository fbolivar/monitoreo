-- =====================================================================
-- 0025_runbooks.up.sql — Auto-remediación / runbooks (#5)
-- Acciones automáticas al abrir una incidencia (webhook a automatización o
-- comando SSH al equipo): reiniciar un servicio, rebotar un puerto, etc.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS runbooks (
  id                    bigserial PRIMARY KEY,
  nombre                text NOT NULL,
  descripcion           text,
  activo                boolean NOT NULL DEFAULT true,
  -- Disparadores (todos opcionales; null = no filtra por ese criterio):
  trigger_tipo_id       smallint REFERENCES tipos_recurso(id) ON DELETE SET NULL,
  trigger_severidad     text CHECK (trigger_severidad IN ('info','warning','critical')),
  trigger_match         text,             -- subcadena que debe contener el título
  -- Acción: jsonb {tipo:'webhook'|'ssh', url?, comando?, ...}. Secretos en `secretos`.
  accion                jsonb NOT NULL DEFAULT '{}'::jsonb,
  secretos              bytea,            -- token webhook / credenciales ssh (pgcrypto)
  cooldown_seg          integer NOT NULL DEFAULT 300,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_runbooks_updated BEFORE UPDATE ON runbooks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS runbook_ejecuciones (
  id            bigserial PRIMARY KEY,
  runbook_id    bigint REFERENCES runbooks(id) ON DELETE CASCADE,
  incidencia_id bigint REFERENCES incidencias(id) ON DELETE SET NULL,
  recurso_id    bigint REFERENCES recursos(id) ON DELETE SET NULL,
  ts            timestamptz NOT NULL DEFAULT now(),
  exito         boolean NOT NULL DEFAULT false,
  salida        text
);
CREATE INDEX IF NOT EXISTS idx_runbook_ejec_runbook ON runbook_ejecuciones(runbook_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_runbook_ejec_recurso ON runbook_ejecuciones(recurso_id, ts DESC);

COMMENT ON TABLE runbooks IS 'Acciones automáticas (auto-remediación) disparadas al abrir incidencias.';

COMMIT;
