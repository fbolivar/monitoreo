-- =====================================================================
-- 0022_incidencias_componente.up.sql
-- Incidencias formales por COMPONENTE de hardware (Redfish/IPMI). Hasta ahora
-- un componente degradado/caído solo generaba un AVISO; ahora abre una
-- incidencia (reconocible/resoluble, en la pantalla Incidencias y wallboard).
-- Se añade la columna `componente` y se amplía el índice único de "una
-- incidencia abierta" a (recurso, interfaz, componente).
-- =====================================================================
BEGIN;

ALTER TABLE incidencias ADD COLUMN IF NOT EXISTS componente text;
COMMENT ON COLUMN incidencias.componente IS
  'Componente físico afectado (p.ej. ''power:PSU1''). NULL = incidencia del recurso o de interfaz.';

-- Una incidencia abierta por (recurso, interfaz, componente). Las existentes
-- (reachability/interfaz) tienen componente NULL -> COALESCE '' (sin cambio).
DROP INDEX IF EXISTS uq_incidencia_abierta;
CREATE UNIQUE INDEX uq_incidencia_abierta
  ON incidencias(recurso_id, COALESCE(if_index, -1), COALESCE(componente, ''))
  WHERE estado <> 'resuelta';

COMMIT;
