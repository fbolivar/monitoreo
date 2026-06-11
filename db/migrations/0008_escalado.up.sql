-- =====================================================================
-- 0008_escalado.up.sql
-- Escalado por tiempo (on-call): marca cuándo se escaló una incidencia por no
-- haberse reconocido a tiempo, para no reescalar en cada ciclo.
-- =====================================================================
BEGIN;
ALTER TABLE incidencias ADD COLUMN IF NOT EXISTS escalada_at timestamptz;
COMMENT ON COLUMN incidencias.escalada_at IS
  'Momento en que se escaló por tiempo (sin reconocer). NULL = aún no escalada.';
COMMIT;
