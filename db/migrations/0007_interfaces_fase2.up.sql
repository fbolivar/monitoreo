-- =====================================================================
-- 0007_interfaces_fase2.up.sql
-- Fase 2 de interfaces:
--  1) Histórico de throughput por interfaz (serie temporal) para graficar.
--  2) Marca `monitorear` por interfaz (uplinks/WAN) para alertar si caen.
--  3) Incidencias por interfaz: if_index/if_nombre + índice único ampliado
--     (una incidencia abierta por (recurso, interfaz); la del recurso usa if_index NULL).
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS interfaces_historico (
  recurso_id bigint NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  if_index   integer NOT NULL,
  ts         timestamptz NOT NULL DEFAULT now(),
  in_mbps    double precision,
  out_mbps   double precision
);
CREATE INDEX IF NOT EXISTS idx_ifhist_recurso_idx_ts
  ON interfaces_historico(recurso_id, if_index, ts DESC);

COMMENT ON TABLE interfaces_historico IS
  'Serie temporal de throughput por interfaz (solo oper-up). Retención corta (purga del worker).';

ALTER TABLE interfaces
  ADD COLUMN IF NOT EXISTS monitorear boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN interfaces.monitorear IS
  'Si true, el worker abre incidencia y notifica cuando esta interfaz pasa a oper-down.';

ALTER TABLE incidencias ADD COLUMN IF NOT EXISTS if_index integer;
ALTER TABLE incidencias ADD COLUMN IF NOT EXISTS if_nombre text;

-- Ampliar la unicidad: una incidencia abierta por (recurso, interfaz).
-- La incidencia "del recurso" usa if_index NULL (COALESCE -> -1).
DROP INDEX IF EXISTS uq_incidencia_abierta;
CREATE UNIQUE INDEX uq_incidencia_abierta
  ON incidencias(recurso_id, COALESCE(if_index, -1))
  WHERE estado <> 'resuelta';

COMMIT;
