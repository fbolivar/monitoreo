-- =====================================================================
-- 0038_disponibilidad_diaria.up.sql
-- Histórico PERMANENTE de disponibilidad por recurso y día.
--
-- Motivo: la disponibilidad se calculaba SIEMPRE desde `chequeos`, que se purga
-- a los 30 días. Es decir: no existía forma de saber la disponibilidad de hace
-- dos meses, ni de comparar meses, ni de sostener un reclamo contractual con
-- histórico — y cada día se perdía un día de evidencia, en silencio.
--
-- Esta tabla la consolida CADA NOCHE (antes de la purga) y se conserva indefinida:
-- ~159 recursos x 365 días = ~58k filas/año, frente a los millones de `chequeos`.
-- Los rollups que ya existían (`metricas_rollup_*`) guardan MÉTRICAS (cpu, latencia),
-- no el estado: no servían para esto.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS disponibilidad_diaria (
  recurso_id     bigint  NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  dia            date    NOT NULL,
  up             integer NOT NULL DEFAULT 0,
  degraded       integer NOT NULL DEFAULT 0,
  down           integer NOT NULL DEFAULT 0,
  unknown        integer NOT NULL DEFAULT 0,
  mantenimiento  integer NOT NULL DEFAULT 0,
  -- (up+degraded)/(up+degraded+down)*100. NULL = sin chequeos evaluables ese día
  -- (p.ej. enlace no medible): NULL es "sin datos", NO 0% — no se inventa una caída.
  disponibilidad numeric(6,3),
  incidencias    integer NOT NULL DEFAULT 0,
  PRIMARY KEY (recurso_id, dia)
);

-- Los informes preguntan por rangos de fechas sobre muchos recursos.
CREATE INDEX IF NOT EXISTS ix_disponibilidad_diaria_dia ON disponibilidad_diaria (dia);

COMMENT ON TABLE  disponibilidad_diaria IS 'Disponibilidad consolidada por recurso y día. Permanente: sobrevive a la purga de chequeos (30d) y sostiene el histórico/tendencia de SLA.';
COMMENT ON COLUMN disponibilidad_diaria.disponibilidad IS 'NULL = sin chequeos evaluables ese día (sin datos), que no es lo mismo que 0%.';

COMMIT;
