#!/usr/bin/env bash
# Elimina todos los canales de notificación de ejemplo.
set -euo pipefail
source /root/monitoreo-secrets.env
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

IDS=$(curl -sk "$API/api/canales-notificacion?per_page=200" -H "$H" \
  | python3 -c "import sys,json;[print(x['id']) for x in json.load(sys.stdin)['data']]")

echo "== Eliminando canales =="
for ID in $IDS; do
  CODE=$(curl -sk -o /dev/null -w '%{http_code}' -X DELETE "$API/api/canales-notificacion/$ID" -H "$H")
  echo "  id $ID -> HTTP $CODE"
done

echo "== Canales restantes =="
curl -sk "$API/api/canales-notificacion?per_page=50" -H "$H" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('  total =',d['total'])"
