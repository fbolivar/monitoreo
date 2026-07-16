-- =====================================================================
-- 0038_disponibilidad_diaria.down.sql
-- OJO: al borrar esta tabla se pierde el histórico de SLA de forma
-- irrecuperable (los `chequeos` de origen ya se purgaron a los 30 días).
-- =====================================================================
BEGIN;

DROP TABLE IF EXISTS disponibilidad_diaria;

COMMIT;
