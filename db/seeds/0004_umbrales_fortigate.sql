-- =====================================================================
-- 0004_umbrales_fortigate.sql  (OPCIONAL — FASE 3b paso 3)
-- Umbrales por defecto SUGERIDOS para firewalls FortiGate (a nivel de tipo).
-- 'sessions' depende del modelo/licencia: ajustar o dejar sin umbral.
-- El estado del clúster HA (operativo/degradado/caído) y el failover los
-- determina el probe, no estos umbrales.
-- Idempotente: ON CONFLICT no duplica.
-- =====================================================================
BEGIN;

INSERT INTO umbrales (tipo_id, metrica, operador, valor_warning, valor_critical, duracion_segundos)
SELECT t.id, x.metrica, x.operador, x.warning, x.critical, x.duracion
FROM (VALUES
    ('firewall', 'cpu', '>', 75, 90, 60),
    ('firewall', 'mem', '>', 80, 90, 60)
    -- Ejemplo de umbral de sesiones (descomentar y ajustar al modelo):
    -- ,('firewall', 'sessions', '>', 500000, 900000, 60)
) AS x(tipo_codigo, metrica, operador, warning, critical, duracion)
JOIN tipos_recurso t ON t.codigo = x.tipo_codigo
ON CONFLICT (tipo_id, metrica) WHERE tipo_id IS NOT NULL DO NOTHING;

COMMIT;
