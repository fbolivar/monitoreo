-- =====================================================================
-- 0002_umbrales_snmp.sql  (OPCIONAL — FASE 3b paso 1)
-- Umbrales por defecto SUGERIDOS para los recursos monitoreados por SNMP.
-- A nivel de TIPO (aplican a todos los recursos del tipo salvo override por recurso).
-- Idempotente: ON CONFLICT no duplica si ya existe el (tipo_id, metrica).
-- =====================================================================
BEGIN;

INSERT INTO umbrales (tipo_id, metrica, operador, valor_warning, valor_critical, duracion_segundos)
SELECT t.id, x.metrica, x.operador, x.warning, x.critical, x.duracion
FROM (VALUES
    -- Servidores
    ('servidor',   'cpu',           '>',  80, 95, 120),
    ('servidor',   'mem',           '>',  85, 95, 120),
    -- Switches LAN
    ('switch_lan', 'cpu',           '>',  80, 95, 120),
    ('switch_lan', 'mem',           '>',  85, 95, 120),
    -- Switches SAN (fibra)
    ('switch_san', 'cpu',           '>',  80, 95, 120),
    ('switch_san', 'mem',           '>',  85, 95, 120),
    -- NAS
    ('nas',        'cpu',           '>',  80, 95, 120),
    ('nas',        'mem',           '>',  85, 95, 120),
    ('nas',        'vol_used',      '>',  80, 90, 0),
    -- UPS (UPS-MIB)
    ('ups',        'bateria',       '<',  50, 20, 0),   -- % carga restante
    ('ups',        'autonomia_min', '<',  10, 5,  0),   -- minutos restantes
    ('ups',        'carga',         '>',  80, 90, 0),   -- % carga de salida
    ('ups',        'estado_linea',  '!=', NULL, 3, 0),  -- 3=normal; distinto => crítico (en batería/bypass)
    ('ups',        'battery_status','>=', 3, 4, 0)      -- 3=low (warning), 4=depleted (crítico)
) AS x(tipo_codigo, metrica, operador, warning, critical, duracion)
JOIN tipos_recurso t ON t.codigo = x.tipo_codigo
ON CONFLICT (tipo_id, metrica) WHERE tipo_id IS NOT NULL DO NOTHING;

COMMIT;
