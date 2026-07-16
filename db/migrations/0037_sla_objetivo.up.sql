-- =====================================================================
-- 0037_sla_objetivo.up.sql
-- Objetivo de disponibilidad (SLA) por tipo de recurso y por recurso.
--
-- Motivo: el informe decía "86,27%" pero no contra QUÉ. Sin un objetivo, el dato
-- es una curiosidad; con él es un incumplimiento medible frente al proveedor o a
-- gerencia. El recurso PISA al tipo (mismo patrón que `umbrales`); NULL = sin
-- objetivo definido -> no se evalúa cumplimiento (no se inventa uno).
-- =====================================================================
BEGIN;

ALTER TABLE tipos_recurso
  ADD COLUMN IF NOT EXISTS sla_objetivo numeric(5,2)
    CHECK (sla_objetivo IS NULL OR (sla_objetivo >= 0 AND sla_objetivo <= 100));

ALTER TABLE recursos
  ADD COLUMN IF NOT EXISTS sla_objetivo numeric(5,2)
    CHECK (sla_objetivo IS NULL OR (sla_objetivo >= 0 AND sla_objetivo <= 100));

COMMENT ON COLUMN tipos_recurso.sla_objetivo IS 'Objetivo de disponibilidad % por defecto para el tipo (NULL = sin objetivo).';
COMMENT ON COLUMN recursos.sla_objetivo      IS 'Objetivo de disponibilidad % del recurso; pisa al del tipo (NULL = hereda).';

COMMIT;
