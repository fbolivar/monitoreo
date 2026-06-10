-- =====================================================================
-- 0002_timeseries.up.sql
-- Serie temporal de métricas + agregación (rollup) + retención escalonada.
--
-- Técnica: particionado declarativo NATIVO de Postgres por RANGE(ts)
-- (mensual). Sin TimescaleDB ni extensiones propietarias -> 100% portable.
--
-- POLÍTICA DE RETENCIÓN ESCALONADA (propuesta; no estaba definida en CLAUDE.md):
--   chequeos (crudo)            ->  30 días
--   metricas (crudo, 1 punto)   ->  15 días
--   metricas_rollup_horario     ->  90 días
--   metricas_rollup_diario      -> 730 días (2 años)
-- Ajustable vía parámetros de fn_purgar_datos().
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Tabla de métricas crudas (serie temporal, particionada por mes)
-- ---------------------------------------------------------------------
CREATE TABLE metricas (
  recurso_id  bigint            NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  metrica     text              NOT NULL,            -- 'cpu','mem','latency','loss','temp','bw_in'...
  valor       double precision  NOT NULL,
  unidad      text,                                  -- '%','ms','C','Mbps'...
  ts          timestamptz       NOT NULL DEFAULT now(),
  PRIMARY KEY (recurso_id, metrica, ts)
) PARTITION BY RANGE (ts);
COMMENT ON TABLE metricas IS 'Métricas crudas en serie temporal, particionadas por mes. Retención: 15 días.';

-- Índice por rango de fechas (consultas "métrica X de recurso Y entre fechas").
-- Definido sobre la tabla madre -> se propaga a todas las particiones.
CREATE INDEX idx_metricas_recurso_metrica_ts ON metricas (recurso_id, metrica, ts DESC);
CREATE INDEX idx_metricas_ts                  ON metricas (ts);

-- Partición DEFAULT: captura cualquier ts sin partición específica (evita
-- fallos de inserción; conviene vaciarla con housekeeping).
CREATE TABLE metricas_default PARTITION OF metricas DEFAULT;

-- ---------------------------------------------------------------------
-- Gestión de particiones mensuales
-- ---------------------------------------------------------------------
-- Crea (si no existe) la partición del mes que contiene p_fecha.
CREATE OR REPLACE FUNCTION fn_crear_particion_metricas(p_fecha date)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_inicio date := date_trunc('month', p_fecha)::date;
  v_fin    date := (date_trunc('month', p_fecha) + interval '1 month')::date;
  v_nombre text := 'metricas_' || to_char(v_inicio, 'YYYY_MM');
BEGIN
  IF to_regclass('public.' || v_nombre) IS NULL THEN
    EXECUTE format(
      'CREATE TABLE %I PARTITION OF metricas FOR VALUES FROM (%L) TO (%L)',
      v_nombre, v_inicio, v_fin);
  END IF;
  RETURN v_nombre;
END;
$$;
COMMENT ON FUNCTION fn_crear_particion_metricas(date) IS
  'Crea la partición mensual de `metricas` que contiene la fecha dada (idempotente). El worker la invoca con antelación.';

-- Elimina particiones mensuales de `metricas` cuyo rango quede totalmente
-- antes de p_antes (housekeeping eficiente alternativo al DELETE).
CREATE OR REPLACE FUNCTION fn_drop_particiones_metricas(p_antes date)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  r       record;
  v_count integer := 0;
BEGIN
  FOR r IN
    SELECT c.relname
    FROM pg_inherits i
    JOIN pg_class c     ON c.oid = i.inhrelid
    JOIN pg_class p     ON p.oid = i.inhparent
    WHERE p.relname = 'metricas'
      AND c.relname ~ '^metricas_\d{4}_\d{2}$'
      AND to_date(right(c.relname, 7), 'YYYY_MM') + interval '1 month' <= p_antes
  LOOP
    EXECUTE format('DROP TABLE IF EXISTS %I', r.relname);
    v_count := v_count + 1;
  END LOOP;
  RETURN v_count;
END;
$$;

-- Pre-crear particiones para mes anterior, actual y siguiente.
SELECT fn_crear_particion_metricas((now() - interval '1 month')::date);
SELECT fn_crear_particion_metricas(now()::date);
SELECT fn_crear_particion_metricas((now() + interval '1 month')::date);

-- ---------------------------------------------------------------------
-- Tablas de ROLLUP (agregados pre-calculados)
-- ---------------------------------------------------------------------
CREATE TABLE metricas_rollup_horario (
  recurso_id bigint            NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  metrica    text              NOT NULL,
  bucket     timestamptz       NOT NULL,             -- date_trunc('hour', ts)
  valor_avg  double precision  NOT NULL,
  valor_min  double precision  NOT NULL,
  valor_max  double precision  NOT NULL,
  valor_sum  double precision  NOT NULL,
  muestras   integer           NOT NULL,
  unidad     text,
  PRIMARY KEY (recurso_id, metrica, bucket)
);
COMMENT ON TABLE metricas_rollup_horario IS 'Agregado horario de métricas. Retención: 90 días.';
CREATE INDEX idx_rollup_hora_bucket ON metricas_rollup_horario (bucket);

CREATE TABLE metricas_rollup_diario (
  recurso_id bigint            NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  metrica    text              NOT NULL,
  bucket     date              NOT NULL,             -- día
  valor_avg  double precision  NOT NULL,
  valor_min  double precision  NOT NULL,
  valor_max  double precision  NOT NULL,
  valor_sum  double precision  NOT NULL,
  muestras   integer           NOT NULL,
  unidad     text,
  PRIMARY KEY (recurso_id, metrica, bucket)
);
COMMENT ON TABLE metricas_rollup_diario IS 'Agregado diario de métricas. Retención: 730 días.';
CREATE INDEX idx_rollup_dia_bucket ON metricas_rollup_diario (bucket);

-- ---------------------------------------------------------------------
-- Funciones de ROLLUP (idempotentes vía UPSERT)
-- ---------------------------------------------------------------------
-- Agrega `metricas` crudas -> rollup horario, en el rango [p_desde, p_hasta).
CREATE OR REPLACE FUNCTION fn_rollup_metricas_horario(
  p_desde timestamptz DEFAULT date_trunc('hour', now() - interval '1 hour'),
  p_hasta timestamptz DEFAULT date_trunc('hour', now())
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE v_filas integer;
BEGIN
  INSERT INTO metricas_rollup_horario AS r
        (recurso_id, metrica, bucket, valor_avg, valor_min, valor_max, valor_sum, muestras, unidad)
  SELECT recurso_id, metrica, date_trunc('hour', ts) AS bucket,
         avg(valor), min(valor), max(valor), sum(valor), count(*)::int, max(unidad)
  FROM metricas
  WHERE ts >= p_desde AND ts < p_hasta
  GROUP BY recurso_id, metrica, date_trunc('hour', ts)
  ON CONFLICT (recurso_id, metrica, bucket) DO UPDATE
    SET valor_avg = EXCLUDED.valor_avg,
        valor_min = EXCLUDED.valor_min,
        valor_max = EXCLUDED.valor_max,
        valor_sum = EXCLUDED.valor_sum,
        muestras  = EXCLUDED.muestras,
        unidad    = EXCLUDED.unidad;
  GET DIAGNOSTICS v_filas = ROW_COUNT;
  RETURN v_filas;
END;
$$;

-- Agrega rollup horario -> rollup diario, en el rango [p_desde, p_hasta) (días).
-- avg ponderado por número de muestras para mantener exactitud.
CREATE OR REPLACE FUNCTION fn_rollup_metricas_diario(
  p_desde date DEFAULT (now() - interval '1 day')::date,
  p_hasta date DEFAULT now()::date
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE v_filas integer;
BEGIN
  INSERT INTO metricas_rollup_diario AS r
        (recurso_id, metrica, bucket, valor_avg, valor_min, valor_max, valor_sum, muestras, unidad)
  SELECT recurso_id, metrica, bucket::date,
         sum(valor_avg * muestras) / NULLIF(sum(muestras), 0),
         min(valor_min), max(valor_max), sum(valor_sum), sum(muestras)::int, max(unidad)
  FROM metricas_rollup_horario
  WHERE bucket >= p_desde AND bucket < p_hasta
  GROUP BY recurso_id, metrica, bucket::date
  ON CONFLICT (recurso_id, metrica, bucket) DO UPDATE
    SET valor_avg = EXCLUDED.valor_avg,
        valor_min = EXCLUDED.valor_min,
        valor_max = EXCLUDED.valor_max,
        valor_sum = EXCLUDED.valor_sum,
        muestras  = EXCLUDED.muestras,
        unidad    = EXCLUDED.unidad;
  GET DIAGNOSTICS v_filas = ROW_COUNT;
  RETURN v_filas;
END;
$$;

-- ---------------------------------------------------------------------
-- PURGA según retención escalonada
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_purgar_datos(
  p_ret_chequeos_dias       integer DEFAULT 30,
  p_ret_metricas_dias       integer DEFAULT 15,
  p_ret_rollup_horario_dias integer DEFAULT 90,
  p_ret_rollup_diario_dias  integer DEFAULT 730
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  v_chequeos bigint;
  v_metricas bigint;
  v_rh       bigint;
  v_rd       bigint;
BEGIN
  DELETE FROM chequeos WHERE ts < now() - make_interval(days => p_ret_chequeos_dias);
  GET DIAGNOSTICS v_chequeos = ROW_COUNT;

  DELETE FROM metricas WHERE ts < now() - make_interval(days => p_ret_metricas_dias);
  GET DIAGNOSTICS v_metricas = ROW_COUNT;

  DELETE FROM metricas_rollup_horario WHERE bucket < now() - make_interval(days => p_ret_rollup_horario_dias);
  GET DIAGNOSTICS v_rh = ROW_COUNT;

  DELETE FROM metricas_rollup_diario WHERE bucket < (now() - make_interval(days => p_ret_rollup_diario_dias))::date;
  GET DIAGNOSTICS v_rd = ROW_COUNT;

  RETURN jsonb_build_object(
    'chequeos_borrados',        v_chequeos,
    'metricas_borradas',        v_metricas,
    'rollup_horario_borrados',  v_rh,
    'rollup_diario_borrados',   v_rd,
    'ejecutado_at',             now()
  );
END;
$$;
COMMENT ON FUNCTION fn_purgar_datos(integer,integer,integer,integer) IS
  'Aplica la retención escalonada. Lo invoca el worker (APScheduler) o pg_cron donde exista.';

-- ---------------------------------------------------------------------
-- Vista de conveniencia: último valor por recurso+métrica
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_ultima_metrica AS
SELECT DISTINCT ON (recurso_id, metrica)
       recurso_id, metrica, valor, unidad, ts
FROM metricas
ORDER BY recurso_id, metrica, ts DESC;

COMMIT;
