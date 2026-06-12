set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
TIPO=$($Pt "SELECT id FROM tipos_recurso WHERE codigo='switch_lan'")
FILTRO="tipo_id=$TIPO AND (hostname LIKE '192.168.10.4%' OR hostname LIKE '192.168.10.5%')"

echo "== 1. Fusionar temp + poe_watts en oids (preserva cpu) =="
$P -c "UPDATE recursos SET parametros = jsonb_set(parametros,'{oids}',
        COALESCE(parametros->'oids','{}'::jsonb) ||
        '{\"temp\":\"1.3.6.1.2.1.99.1.1.1.4.3\",\"poe_watts\":\"1.3.6.1.2.1.105.1.3.1.1.4.1\"}'::jsonb)
       WHERE $FILTRO"

echo "== 2. Fusionar poe (%) en oids_pct (preserva mem) =="
$P -c "UPDATE recursos SET parametros = jsonb_set(parametros,'{oids_pct}',
        COALESCE(parametros->'oids_pct','{}'::jsonb) ||
        '{\"poe\":{\"used\":\"1.3.6.1.2.1.105.1.3.1.1.4.1\",\"total\":\"1.3.6.1.2.1.105.1.3.1.1.2.1\"}}'::jsonb)
       WHERE $FILTRO"

echo "== 3. Umbrales tipo switch_lan: temp (55/68) y poe (85/95), persistencia 120s =="
$P -c "DELETE FROM umbrales WHERE tipo_id=$TIPO AND metrica IN ('temp','poe') AND recurso_id IS NULL"
$P -c "INSERT INTO umbrales (tipo_id, metrica, operador, valor_warning, valor_critical, duracion_segundos, activo) VALUES
        ($TIPO,'temp','>',55,68,120,true),
        ($TIPO,'poe','>',85,95,120,true)"

echo "== 4. Reiniciar worker + rechequear =="
systemctl restart monitoreo-worker; sleep 3
IDS=$($Pt "SELECT id FROM recursos WHERE $FILTRO")
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $IDS >/dev/null 2>&1 )
sleep 1

echo "== 5. Temp / PoE por switch =="
$P -c "SELECT r.nombre,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='cpu' ORDER BY ts DESC LIMIT 1) AS cpu,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='mem' ORDER BY ts DESC LIMIT 1) AS mem,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='temp' ORDER BY ts DESC LIMIT 1) AS temp_c,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='poe_watts' ORDER BY ts DESC LIMIT 1) AS poe_w,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='poe' ORDER BY ts DESC LIMIT 1) AS poe_pct
       FROM recursos r WHERE $FILTRO ORDER BY r.hostname"
