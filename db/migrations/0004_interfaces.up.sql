-- =====================================================================
-- 0004_interfaces.up.sql
-- Snapshot del estado actual de interfaces de red (IF-MIB) por recurso.
-- Se actualiza (upsert) en cada ciclo de chequeo de los recursos con
-- parametros.interfaces = true. El throughput (Mbps) se calcula en el worker
-- por delta de contadores HC; aquí solo se guarda el último valor.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS interfaces (
  recurso_id    bigint   NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  if_index      integer  NOT NULL,
  if_name       text,
  admin_estado  text,                 -- up | down
  oper_estado   text,                 -- up | down
  speed_mbps    double precision,     -- ifHighSpeed
  in_mbps       double precision,     -- tráfico entrante (delta de octetos)
  out_mbps      double precision,     -- tráfico saliente
  util_in       double precision,     -- % de la velocidad
  util_out      double precision,
  in_err        bigint,               -- errores entrantes en el intervalo
  out_err       bigint,               -- errores salientes en el intervalo
  ts            timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (recurso_id, if_index)
);

CREATE INDEX IF NOT EXISTS idx_interfaces_recurso ON interfaces(recurso_id);

COMMENT ON TABLE interfaces IS 'Estado actual (snapshot) de interfaces de red por recurso (IF-MIB).';

COMMIT;
