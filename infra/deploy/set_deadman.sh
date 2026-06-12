#!/usr/bin/env bash
set -uo pipefail
ENV=/opt/monitoreo/monitor/.env
URL="https://hc-ping.com/917fc58f-f4be-4295-b7d1-8740cb63ba4f"
# no duplicar si ya existe
grep -q '^DEADMAN_URL=' "$ENV" && sed -i '/^DEADMAN_URL=/d' "$ENV"
grep -q '^DEADMAN_INTERVAL_SEG=' "$ENV" && sed -i '/^DEADMAN_INTERVAL_SEG=/d' "$ENV"
printf '\nDEADMAN_URL=%s\nDEADMAN_INTERVAL_SEG=60\n' "$URL" >> "$ENV"
echo "== .env (deadman) =="
grep -nE 'DEADMAN' "$ENV"
echo "== ping manual de prueba a healthchecks =="
curl -fsS --max-time 10 "$URL" && echo " -> ping OK"
echo "== reiniciar worker =="
systemctl restart monitoreo-worker
sleep 3
systemctl is-active monitoreo-worker
echo "== logs del worker (latido/deadman, ultimos 70s) =="
journalctl -u monitoreo-worker --since '70 seconds ago' --no-pager | grep -iE 'deadman|latido|dead-man' | tail -10 || echo '(sin lineas aun)'
