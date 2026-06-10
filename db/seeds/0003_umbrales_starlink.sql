-- =====================================================================
-- 0003_umbrales_starlink.sql  (OPCIONAL — FASE 3b paso 2)
-- Umbrales por defecto SUGERIDOS para enlaces Starlink (a nivel de tipo).
-- throughput_* dependen del plan contratado: ajustar según el caso.
-- Idempotente: ON CONFLICT no duplica.
-- =====================================================================
BEGIN;

INSERT INTO umbrales (tipo_id, metrica, operador, valor_warning, valor_critical, duracion_segundos)
SELECT t.id, x.metrica, x.operador, x.warning, x.critical, x.duracion
FROM (VALUES
    ('starlink', 'latency',         '>',  150, 400, 60),  -- ms
    ('starlink', 'loss',            '>',  2,   10,  60),  -- % pérdida
    ('starlink', 'obstruccion',     '>',  1,   5,   0),   -- % cielo obstruido
    ('starlink', 'throughput_down', '<',  20,  5,   60)   -- Mbps (ajustar al plan)
) AS x(tipo_codigo, metrica, operador, warning, critical, duracion)
JOIN tipos_recurso t ON t.codigo = x.tipo_codigo
ON CONFLICT (tipo_id, metrica) WHERE tipo_id IS NOT NULL DO NOTHING;

COMMIT;
