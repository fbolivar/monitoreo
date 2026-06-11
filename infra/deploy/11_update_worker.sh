#!/usr/bin/env bash
# Actualiza el worker desde GitHub y lo reinicia.
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc"

cd /opt/monitoreo
git pull --ff-only origin main
git log --oneline -1

echo -n "chequeos ANTES: "; $PSQL "SELECT count(*) FROM chequeos"
systemctl restart monitoreo-worker
echo "worker reiniciado; esperando 40s para un ciclo de chequeos…"
sleep 40

echo -n "chequeos DESPUÉS: "; $PSQL "SELECT count(*) FROM chequeos"
echo "estado_actual de recursos:"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT estado_actual, count(*) FROM recursos GROUP BY estado_actual ORDER BY 2 DESC"
echo "== últimos chequeos (logs) =="
journalctl -u monitoreo-worker --no-pager -n 8 | grep -E "Chequeo" | tail -8 || echo "(sin logs Chequeo aún)"
