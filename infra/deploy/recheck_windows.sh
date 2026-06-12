#!/usr/bin/env bash
# Fuerza chequeo del Windows y muestra estado + métricas. Env: IP.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
RID=$($Pt "SELECT id FROM recursos WHERE hostname='${IP:?}' ORDER BY id DESC LIMIT 1")
echo "recurso id=$RID"
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py "$RID" 2>&1 | tail -1 )
$P -c "SELECT nombre, hostname, estado_actual FROM recursos WHERE id=$RID"
echo "== Métricas (CPU / memoria) =="
$P -c "SELECT metrica, valor, unidad FROM metricas WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 5"
echo -n "interfaces detectadas: "; $Pt "SELECT count(*) FROM interfaces WHERE recurso_id=$RID"
