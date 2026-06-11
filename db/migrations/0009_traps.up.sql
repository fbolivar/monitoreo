-- =====================================================================
-- 0009_traps.up.sql
-- Recepción de SNMP traps (eventos asíncronos enviados por los equipos):
-- link down/up, cold/warm start, fallas de hardware, etc. Complementa el
-- sondeo periódico con detección en TIEMPO REAL. Lo escribe el servicio
-- simon-traps (receptor pysnmp), no la API ni el worker de sondeo.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS traps (
  id          bigserial PRIMARY KEY,
  ts          timestamptz NOT NULL DEFAULT now(),
  source_ip   inet,
  recurso_id  bigint REFERENCES recursos(id) ON DELETE SET NULL,
  trap_oid    text,
  nombre      text,            -- etiqueta legible (linkDown, coldStart, ...)
  severidad   text NOT NULL DEFAULT 'info',  -- info | warning | critical
  descripcion text,
  varbinds    jsonb
);

CREATE INDEX IF NOT EXISTS idx_traps_ts ON traps(ts DESC);
CREATE INDEX IF NOT EXISTS idx_traps_recurso ON traps(recurso_id, ts DESC);

COMMENT ON TABLE traps IS 'SNMP traps recibidos (eventos en tiempo real de los equipos).';

COMMIT;
