-- =====================================================================
-- 0051_mapas_personalizados.up.sql
-- Mapas personalizados (estilo Network Atlas / PRTG maps): un lienzo donde el
-- operador coloca recursos como nodos (con semáforo en vivo), los conecta con
-- líneas y pone un fondo opcional (plano/diagrama). El layout (nodos + enlaces)
-- se guarda como jsonb; el estado de cada nodo se pinta en vivo desde el recurso.
-- Son compartidos (vistas de equipo): lectura para todos, gestión admin/operador.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS mapas (
  id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre     text        NOT NULL,
  fondo_url  text,                                   -- imagen de fondo opcional (URL)
  ancho      integer     NOT NULL DEFAULT 1200,      -- espacio de coordenadas del lienzo
  alto       integer     NOT NULL DEFAULT 700,
  layout     jsonb       NOT NULL DEFAULT '{"nodos":[],"enlaces":[]}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE mapas IS 'Mapas personalizados: nodos (recursos/texto) + enlaces en un lienzo, con estado en vivo.';

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitoreo') THEN
    EXECUTE 'ALTER TABLE mapas OWNER TO monitoreo';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    EXECUTE 'GRANT SELECT ON mapas TO grafana_ro';
  END IF;
END $$;

COMMIT;
