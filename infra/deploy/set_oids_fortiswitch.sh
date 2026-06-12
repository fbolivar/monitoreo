#!/usr/bin/env bash
# Configura los OIDs de monitoreo de los 14 FortiSwitch de piso (192.168.10.41-54):
#   - cpu (%)  = 1.3.6.1.4.1.12356.106.4.1.2.0   (FORTINET-FORTISWITCH-MIB fsSysCpuUsage)
#   - mem (%)  = derivada usado/total (oids_pct):
#                used  = ...106.4.1.3.0  (KB)
#                total = ...106.4.1.4.0  (KB, ~491048 = 480MB en el 148F)
# El OID de cpu anterior estaba MAL (apuntaba a Dell/Force10 6027, herencia de cuando
# se creyó que eran Dell). Requiere snmp.py con soporte oids_pct.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
TIPO=$($Pt "SELECT id FROM tipos_recurso WHERE codigo='switch_lan'")

echo "== oids (cpu) + oids_pct (mem) en los 14 FortiSwitch (.10.41-.54, no el core .10.1) =="
$P -c "UPDATE recursos
       SET parametros = jsonb_set(
             jsonb_set(parametros, '{oids}', '{\"cpu\":\"1.3.6.1.4.1.12356.106.4.1.2.0\"}'::jsonb),
             '{oids_pct}', '{\"mem\":{\"used\":\"1.3.6.1.4.1.12356.106.4.1.3.0\",\"total\":\"1.3.6.1.4.1.12356.106.4.1.4.0\"}}'::jsonb)
       WHERE tipo_id=$TIPO AND (hostname LIKE '192.168.10.4%' OR hostname LIKE '192.168.10.5%')"

echo "== Umbrales de tipo switch_lan: cpu (85/95) y mem (90/97), persistencia 120s =="
$P -c "DELETE FROM umbrales WHERE tipo_id=$TIPO AND metrica IN ('cpu','mem') AND recurso_id IS NULL"
$P -c "INSERT INTO umbrales (tipo_id, metrica, operador, valor_warning, valor_critical, duracion_segundos, activo) VALUES
        ($TIPO,'cpu','>',85,95,120,true),
        ($TIPO,'mem','>',90,97,120,true)"

echo "== Reiniciar worker (carga snmp.py con oids_pct) y rechequear =="
systemctl restart monitoreo-worker; sleep 3
IDS=$($Pt "SELECT id FROM recursos WHERE tipo_id=$TIPO AND (hostname LIKE '192.168.10.4%' OR hostname LIKE '192.168.10.5%')")
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $IDS >/dev/null 2>&1 )
sleep 1

echo "== CPU / Mem% por switch =="
$P -c "SELECT r.nombre,
          (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='cpu' ORDER BY ts DESC LIMIT 1) AS cpu_pct,
          (SELECT round(valor::numeric,1) FROM metricas WHERE recurso_id=r.id AND metrica='mem' ORDER BY ts DESC LIMIT 1) AS mem_pct
       FROM recursos r WHERE r.tipo_id=$TIPO AND (r.hostname LIKE '192.168.10.4%' OR r.hostname LIKE '192.168.10.5%')
       ORDER BY r.hostname"
