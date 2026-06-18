-- =====================================================================
-- 0026_cumplimiento.up.sql — Cumplimiento de configuración (#7)
-- Valida la última config respaldada (config_respaldos) contra políticas
-- (golden config): debe/no debe contener X, o cumplir una regex. Avisa al
-- incumplir. Estilo SolarWinds NCM / Oxidized+compliance.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS cumplimiento_politicas (
  id            bigserial PRIMARY KEY,
  nombre        text NOT NULL,
  descripcion   text,
  tipo          text NOT NULL CHECK (tipo IN ('contiene','no_contiene','regex')),
  patron        text NOT NULL,
  severidad     text NOT NULL DEFAULT 'warning' CHECK (severidad IN ('info','warning','critical')),
  aplica_tipo_id smallint REFERENCES tipos_recurso(id) ON DELETE SET NULL,  -- null = todos
  activo        boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_cumpl_pol_updated BEFORE UPDATE ON cumplimiento_politicas
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS cumplimiento_resultados (
  id            bigserial PRIMARY KEY,
  recurso_id    bigint NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  politica_id   bigint NOT NULL REFERENCES cumplimiento_politicas(id) ON DELETE CASCADE,
  cumple        boolean NOT NULL,
  detalle       text,
  ts            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (recurso_id, politica_id)
);
CREATE INDEX IF NOT EXISTS idx_cumpl_res_recurso ON cumplimiento_resultados(recurso_id);

COMMENT ON TABLE cumplimiento_politicas IS 'Políticas de cumplimiento de configuración (golden config).';

COMMIT;
