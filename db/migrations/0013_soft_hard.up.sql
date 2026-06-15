-- =====================================================================
-- 0013_soft_hard.up.sql
-- Estados SOFT/HARD (estilo Nagios/Checkmk): un estado "malo" (down/degraded/
-- unknown) solo se confirma como HARD tras N chequeos consecutivos. Solo las
-- transiciones HARD abren/cierran incidencias y notifican. Esto mata los
-- falsos positivos por un timeout/paquete perdido puntual (clave con Starlink).
--
-- `estado_actual` pasa a reflejar el estado HARD (dashboard estable). El estado
-- crudo de cada chequeo se sigue guardando en `chequeos` con su valor real.
-- =====================================================================
BEGIN;

ALTER TABLE recursos
  -- Estado confirmado (HARD). Lo que ve el dashboard y lo que dispara incidencias.
  ADD COLUMN IF NOT EXISTS estado_hard text NOT NULL DEFAULT 'unknown'
    CHECK (estado_hard IN ('up','degraded','down','unknown','maintenance')),
  -- Candidato en confirmación (SOFT): el estado crudo que se está confirmando.
  ADD COLUMN IF NOT EXISTS estado_candidato text NOT NULL DEFAULT 'unknown'
    CHECK (estado_candidato IN ('up','degraded','down','unknown','maintenance')),
  -- Chequeos consecutivos del candidato actual hacia su confirmación.
  ADD COLUMN IF NOT EXISTS intentos_estado integer NOT NULL DEFAULT 0
    CHECK (intentos_estado >= 0),
  -- Override por recurso del nº de confirmaciones (NULL = usa el default global del worker).
  ADD COLUMN IF NOT EXISTS max_check_attempts smallint
    CHECK (max_check_attempts IS NULL OR max_check_attempts BETWEEN 1 AND 10);

-- Inicializa el estado HARD/candidato de los recursos existentes con su estado actual.
UPDATE recursos SET estado_hard = estado_actual, estado_candidato = estado_actual;

COMMENT ON COLUMN recursos.estado_hard IS 'Estado confirmado (HARD). Dispara incidencias; alimenta estado_actual.';
COMMENT ON COLUMN recursos.estado_candidato IS 'Estado crudo en confirmación (SOFT) aún no consolidado como HARD.';
COMMENT ON COLUMN recursos.intentos_estado IS 'Chequeos consecutivos del candidato hacia su confirmación HARD.';
COMMENT ON COLUMN recursos.max_check_attempts IS 'Override por recurso del nº de confirmaciones; NULL = default global (MAX_CHECK_ATTEMPTS).';

COMMIT;
