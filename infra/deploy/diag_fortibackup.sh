#!/usr/bin/env bash
# Diagnostica el endpoint de backup de config del FortiGate. Env: TOK (api_key).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
H=$(psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc \
  "SELECT hostname FROM recursos WHERE tipo_id=(SELECT id FROM tipos_recurso WHERE codigo='firewall') ORDER BY id LIMIT 1")
base="https://$H"
echo "=== POST ?scope=global ==="
curl -sk -o /tmp/c1.txt -w 'HTTP %{http_code} bytes %{size_download}\n' -X POST \
  "$base/api/v2/monitor/system/config/backup?scope=global" -H "Authorization: Bearer $TOK"
head -c 120 /tmp/c1.txt; echo; echo
echo "=== POST body {scope:global} ==="
curl -sk -o /tmp/c2.txt -w 'HTTP %{http_code} bytes %{size_download}\n' -X POST \
  "$base/api/v2/monitor/system/config/backup" -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' -d '{"scope":"global"}'
head -c 120 /tmp/c2.txt; echo
