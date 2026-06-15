-- =====================================================================
-- 0015_pronosticos.up.sql
-- Forecasting de capacidad (estilo timeleft()/forecast() de Zabbix).
-- El worker ajusta una regresión lineal sobre `metricas_rollup_diario` de las
-- métricas de capacidad (disco_*, mem) y proyecta cuántos días faltan para
-- llegar al techo (100%). Guarda el último pronóstico por (recurso, métrica) y
-- avisa (sin incidencia) cuando dias_restantes cruza por debajo del umbral.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS pronosticos (
  recurso_id     bigint            NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  metrica        text              NOT NULL,
  ts             timestamptz       NOT NULL DEFAULT now(),  -- cuándo se calculó
  valor_actual   double precision  NOT NULL,                -- último avg diario
  pendiente_dia  double precision  NOT NULL,                -- unidades/día (regresión)
  dias_restantes double precision,                          -- NULL = estable/bajando o sin confianza
  techo          double precision  NOT NULL DEFAULT 100,    -- límite (100% para discos/mem)
  r2             double precision,                          -- confianza del ajuste [0..1]
  muestras       integer           NOT NULL,                -- días usados en el ajuste
  PRIMARY KEY (recurso_id, metrica)
);
COMMENT ON TABLE pronosticos IS 'Último pronóstico de capacidad por recurso+métrica (regresión sobre rollup diario).';
COMMENT ON COLUMN pronosticos.dias_restantes IS 'Días estimados para llegar al techo; NULL si estable/bajando o ajuste poco fiable.';

CREATE INDEX IF NOT EXISTS idx_pronosticos_dias ON pronosticos(dias_restantes)
  WHERE dias_restantes IS NOT NULL;

COMMIT;
