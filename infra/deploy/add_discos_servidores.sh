set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
echo "== Verificar snmp.py nuevo (construir_muestras_discos) =="
grep -c "construir_muestras_discos" /opt/monitoreo/monitor/monitor/probes/snmp.py
TIPO=$($Pt "SELECT id FROM tipos_recurso WHERE codigo='servidor'")
echo "== Umbral tipo servidor: disco_max (90/96 %), persistencia 300s =="
$P -c "DELETE FROM umbrales WHERE tipo_id=$TIPO AND metrica='disco_max' AND recurso_id IS NULL"
$P -c "INSERT INTO umbrales (tipo_id, metrica, operador, valor_warning, valor_critical, duracion_segundos, activo)
       VALUES ($TIPO,'disco_max','>',90,96,300,true)"
echo "== Reiniciar worker + rechequear los 11 servidores =="
systemctl restart monitoreo-worker; sleep 3; systemctl is-active monitoreo-worker
IDS=$($Pt "SELECT id FROM recursos WHERE tipo_id=$TIPO AND activo")
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $IDS >/dev/null 2>&1 )
sleep 1
echo "== Discos por servidor (% usado) =="
$P -c "SELECT r.nombre,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='cpu' ORDER BY ts DESC LIMIT 1) AS cpu,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='mem' ORDER BY ts DESC LIMIT 1) AS mem,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='disco_C' ORDER BY ts DESC LIMIT 1) AS c,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='disco_D' ORDER BY ts DESC LIMIT 1) AS d,
        (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='disco_max' ORDER BY ts DESC LIMIT 1) AS peor
       FROM recursos r WHERE r.tipo_id=$TIPO AND r.activo ORDER BY r.nombre"
