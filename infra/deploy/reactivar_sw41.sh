#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"

echo "== Reactivar SW-PISO1-NC-41 (.10.41) =="
$P -c "UPDATE recursos SET activo=true WHERE hostname='192.168.10.41'"

ID=$($Pt "SELECT id FROM recursos WHERE hostname='192.168.10.41' LIMIT 1")
echo "id=$ID -> chequeo inmediato"
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py "$ID" >/dev/null 2>&1 )
sleep 1

echo "== Estado tras el chequeo =="
$P -c "SELECT r.id, r.nombre, r.hostname, r.activo, r.estado_actual,
          (SELECT estado FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) AS ult_chequeo,
          (SELECT count(*) FROM interfaces WHERE recurso_id=r.id) AS ifaces
       FROM recursos r WHERE r.hostname='192.168.10.41'"

echo "== Incidencias abiertas de este switch (deberían cerrarse) =="
$P -c "SELECT id, estado, severidad, titulo, abierta_at FROM incidencias WHERE recurso_id=$ID AND estado!='resuelta'"
