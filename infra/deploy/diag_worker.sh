#!/usr/bin/env bash
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc"
echo "== uptime servicio =="
systemctl show monitoreo-worker -p ActiveEnterTimestamp -p NRestarts
echo "== último chequeo (ts) =="
$PSQL "SELECT max(ts) FROM chequeos"
echo "== chequeos por minuto (últimos) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT date_trunc('minute',ts) m, count(*) FROM chequeos GROUP BY m ORDER BY m DESC LIMIT 6"
echo "== journal worker (últimas 30) =="
journalctl -u monitoreo-worker --no-pager -n 30 --since "-10 min" | tail -30
