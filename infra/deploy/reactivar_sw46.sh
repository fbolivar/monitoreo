#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
$P -c "UPDATE recursos SET activo=true WHERE hostname='192.168.10.46'"
ID=$($Pt "SELECT id FROM recursos WHERE hostname='192.168.10.46' LIMIT 1")
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py "$ID" >/dev/null 2>&1 )
sleep 1
$P -c "SELECT r.id, r.nombre, r.hostname, r.activo, r.estado_actual,
          (SELECT estado FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) AS ult,
          (SELECT count(*) FROM interfaces WHERE recurso_id=r.id) AS ifaces
       FROM recursos r WHERE r.hostname='192.168.10.46'"
$P -c "SELECT count(*) AS incidencias_abiertas FROM incidencias WHERE recurso_id=$ID AND estado!='resuelta'"
