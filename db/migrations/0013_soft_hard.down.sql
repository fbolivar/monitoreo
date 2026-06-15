-- =====================================================================
-- 0013_soft_hard.down.sql — Reversa de 0013_soft_hard.up.sql
-- =====================================================================
BEGIN;
ALTER TABLE recursos
  DROP COLUMN IF EXISTS estado_hard,
  DROP COLUMN IF EXISTS estado_candidato,
  DROP COLUMN IF EXISTS intentos_estado,
  DROP COLUMN IF EXISTS max_check_attempts;
COMMIT;
