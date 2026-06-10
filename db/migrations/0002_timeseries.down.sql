-- =====================================================================
-- 0002_timeseries.down.sql  — Reversa de 0002_timeseries.up.sql
-- =====================================================================
BEGIN;

DROP VIEW IF EXISTS vw_ultima_metrica;

DROP FUNCTION IF EXISTS fn_purgar_datos(integer,integer,integer,integer);
DROP FUNCTION IF EXISTS fn_rollup_metricas_diario(date, date);
DROP FUNCTION IF EXISTS fn_rollup_metricas_horario(timestamptz, timestamptz);
DROP FUNCTION IF EXISTS fn_drop_particiones_metricas(date);
DROP FUNCTION IF EXISTS fn_crear_particion_metricas(date);

DROP TABLE IF EXISTS metricas_rollup_diario;
DROP TABLE IF EXISTS metricas_rollup_horario;

-- Al borrar la tabla madre se eliminan todas sus particiones (mensuales + default).
DROP TABLE IF EXISTS metricas;

COMMIT;
