#!/usr/bin/env bash
# Elimina TODOS los recursos de ejemplo del seed, dejando solo FortiGate-Principal.
set -euo pipefail
source /root/monitoreo-secrets.env
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

IDS=$(curl -sk "$API/api/recursos?per_page=500" -H "$H" \
  | python3 -c "import sys,json;[print(x['id']) for x in json.load(sys.stdin)['data'] if x['nombre']!='FortiGate-Principal']")

echo "== Eliminando recursos de ejemplo =="
for ID in $IDS; do
  CODE=$(curl -sk -o /dev/null -w '%{http_code}' -X DELETE "$API/api/recursos/$ID" -H "$H")
  echo "  id $ID -> HTTP $CODE"
done

echo "== Inventario resultante =="
curl -sk "$API/api/recursos?per_page=50" -H "$H" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);[print('  -',x['id'],x['nombre'],'->',x['estado_actual']) for x in d['data']];print('  TOTAL =',d['total'])"
