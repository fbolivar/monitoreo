-- =====================================================================
-- 0050_syslog_reglas.up.sql
-- Reglas syslog patrón→incidencia (cierra el ciclo de P0-3). Una regla casa un
-- patrón (regex) contra el mensaje/app/hostname y ABRE o CIERRA una incidencia
-- formal en el recurso mapeado, igual que linkDown/linkUp de traps. La `clave`
-- vincula abrir↔cerrar (se usa como componente='syslog:<clave>').
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS syslog_reglas (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre      text        NOT NULL,
  activo      boolean     NOT NULL DEFAULT true,
  campo       text        NOT NULL DEFAULT 'mensaje' CHECK (campo IN ('mensaje','app','hostname')),
  patron      text        NOT NULL,                  -- regex (sintaxis Python)
  accion      text        NOT NULL CHECK (accion IN ('abrir','cerrar')),
  severidad   text        CHECK (severidad IN ('warning','critical')),   -- para 'abrir'
  clave       text        NOT NULL,                  -- liga abrir/cerrar (componente='syslog:'||clave)
  notificar   boolean     NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE syslog_reglas IS 'Reglas patrón→incidencia para eventos syslog (abrir/cerrar por regex).';

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitoreo') THEN
    EXECUTE 'ALTER TABLE syslog_reglas OWNER TO monitoreo';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    EXECUTE 'GRANT SELECT ON syslog_reglas TO grafana_ro';
  END IF;
END $$;

COMMIT;
