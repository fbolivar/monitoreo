#!/usr/bin/env bash
set -euo pipefail
source /root/monitoreo-secrets.env
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

echo "== Sitios actuales =="
curl -sk "$API/api/sitios?per_page=50" -H "$H" \
  | python3 -c "import sys,json;[print(' ',x['id'],x['codigo'],x['nombre']) for x in json.load(sys.stdin)['data']]"

echo "== Crear sitio de prueba =="
ID=$(curl -sk -X POST "$API/api/sitios" -H "$H" -H 'Content-Type: application/json' \
  -d '{"codigo":"TST-CRUD","nombre":"Sitio de prueba CRUD","ciudad":"Bogota","activo":true}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))")
echo "  creado id=$ID"

echo "== Editar =="
curl -sk -o /dev/null -w "  PUT -> HTTP %{http_code}\n" -X PUT "$API/api/sitios/$ID" -H "$H" -H 'Content-Type: application/json' \
  -d '{"nombre":"Sitio de prueba (editado)","ciudad":"Medellin"}'

echo "== Eliminar =="
curl -sk -o /dev/null -w "  DELETE -> HTTP %{http_code}\n" -X DELETE "$API/api/sitios/$ID" -H "$H"
