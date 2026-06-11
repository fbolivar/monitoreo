#!/usr/bin/env bash
# Elimina los firewalls de ejemplo del seed (IPs falsas) vía la API.
set -euo pipefail
source /root/monitoreo-secrets.env
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

for N in "FortiGate-DC-01" "FortiGate-Sede"; do
  ID=$(curl -sk "$API/api/recursos?per_page=200" -H "$H" \
    | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(next((x['id'] for x in d if x['nombre']=='$N'),''))")
  if [ -n "$ID" ]; then
    CODE=$(curl -sk -o /dev/null -w '%{http_code}' -X DELETE "$API/api/recursos/$ID" -H "$H")
    echo "Eliminado $N (id $ID) -> HTTP $CODE"
  else
    echo "$N no encontrado (¿ya eliminado?)"
  fi
done

echo "== Firewalls restantes =="
curl -sk "$API/api/recursos?tipo_id=1&per_page=50" -H "$H" \
  | python3 -c "import sys,json;[print(' ',x['id'],x['nombre'],'->',x['estado_actual']) for x in json.load(sys.stdin)['data']]"
echo "== Total de recursos =="
curl -sk "$API/api/recursos?per_page=1" -H "$H" | python3 -c "import sys,json;print(' total =',json.load(sys.stdin)['total'])"
