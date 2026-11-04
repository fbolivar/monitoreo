-- =====================================================================
-- 0049_dashboards.up.sql
-- Dashboards personalizables por usuario. Cada usuario arma sus tableros a partir
-- de widgets (KPIs, semáforo por sitio, incidencias, métrica, syslog). El layout
-- completo se guarda como jsonb (lista ordenada de widgets con su tipo/ancho/config).
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS dashboards (
  id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  perfil_id  uuid        NOT NULL REFERENCES perfiles(id) ON DELETE CASCADE,
  nombre     text        NOT NULL,
  es_default boolean     NOT NULL DEFAULT false,
  widgets    jsonb       NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dashboards_perfil ON dashboards (perfil_id);
COMMENT ON TABLE dashboards IS 'Tableros personalizables por usuario (widgets en jsonb).';

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitoreo') THEN
    EXECUTE 'ALTER TABLE dashboards OWNER TO monitoreo';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    EXECUTE 'GRANT SELECT ON dashboards TO grafana_ro';
  END IF;
END $$;

COMMIT;
