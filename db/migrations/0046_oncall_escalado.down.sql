-- =====================================================================
-- 0046_oncall_escalado.down.sql
-- =====================================================================
BEGIN;

ALTER TABLE incidencias DROP COLUMN IF EXISTS nivel_escalado;
DROP TABLE IF EXISTS escalado_niveles;
DROP TABLE IF EXISTS politicas_escalado;
DROP TABLE IF EXISTS turno_participantes;
DROP TABLE IF EXISTS turnos_oncall;

COMMIT;
