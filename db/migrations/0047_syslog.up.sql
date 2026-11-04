-- =====================================================================
-- 0047_syslog.up.sql
-- Ingesta de SYSLOG (NOC P0-3). Servicio aparte (simon-syslog) que escucha
-- UDP/514, parsea RFC3164/RFC5424, mapea IP de origen -> recurso y clasifica la
-- severidad. Complementa SNMP traps y el sondeo: muchos equipos de red solo
-- "hablan" por syslog. Alta rotación -> retención corta (purga del worker).
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS syslog_eventos (
  id               bigserial   PRIMARY KEY,
  ts               timestamptz NOT NULL DEFAULT now(),   -- recepción
  source_ip        inet,
  recurso_id       bigint      REFERENCES recursos(id) ON DELETE SET NULL,
  facility         smallint,                             -- 0..23 (del PRI)
  severidad_syslog smallint,                             -- 0..7 (del PRI, crudo)
  severidad        text NOT NULL DEFAULT 'info',         -- info | warning | critical (nuestra)
  hostname         text,                                 -- host del mensaje
  app              text,                                 -- tag / app-name
  mensaje          text
);
CREATE INDEX IF NOT EXISTS ix_syslog_ts       ON syslog_eventos (ts DESC);
CREATE INDEX IF NOT EXISTS ix_syslog_recurso  ON syslog_eventos (recurso_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_syslog_sev      ON syslog_eventos (severidad) WHERE severidad <> 'info';

COMMENT ON TABLE syslog_eventos IS 'Eventos syslog recibidos (UDP/514). Retención corta; alta rotación.';

-- Dueño/grant para el rol de la app (defensivo si se aplica como 'postgres').
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitoreo') THEN
    EXECUTE 'ALTER TABLE syslog_eventos OWNER TO monitoreo';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    EXECUTE 'GRANT SELECT ON syslog_eventos TO grafana_ro';
  END IF;
END $$;

COMMIT;
