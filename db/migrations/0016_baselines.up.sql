-- =====================================================================
-- 0016_baselines.up.sql
-- Línea base estacional (umbral dinámico) para detección de anomalías.
-- El worker calcula, por (recurso, métrica, hora-del-día UTC), la media y la
-- desviación típica del histórico horario (metricas_rollup_horario). En el
-- chequeo en vivo, una métrica que se dispara muy por encima de su banda normal
-- de esa hora se marca como anomalía -> degradado (estilo Datadog/Dynatrace).
--
-- Es OPT-IN por recurso: solo se evalúan las métricas listadas en
-- parametros.baseline_metricas (p.ej. {"baseline_metricas":["cpu","mem"]}).
-- Guardas anti-ruido: nº mínimo de muestras por franja, k·σ (def 3), piso
-- absoluto de desviación, y confirmación SOFT/HARD (un pico aislado no alerta).
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS baselines (
  recurso_id     bigint            NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  metrica        text              NOT NULL,
  hora           smallint          NOT NULL CHECK (hora BETWEEN 0 AND 23),  -- hora del día (UTC)
  media          double precision  NOT NULL,
  desviacion     double precision  NOT NULL DEFAULT 0,   -- stddev muestral (0 si constante)
  muestras       integer           NOT NULL,             -- días que aportaron a esta franja
  actualizado_at timestamptz       NOT NULL DEFAULT now(),
  PRIMARY KEY (recurso_id, metrica, hora)
);
COMMENT ON TABLE baselines IS 'Línea base por recurso+métrica+hora (media/σ del histórico horario). Umbral dinámico.';
COMMENT ON COLUMN baselines.hora IS 'Hora del día en UTC (0-23); consistente con el bucket del rollup horario.';

CREATE INDEX IF NOT EXISTS idx_baselines_recurso ON baselines(recurso_id);

COMMIT;
