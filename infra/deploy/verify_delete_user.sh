#!/usr/bin/env bash
# Verifica el borrado de usuarios: anti-self (422), anti-último-admin, y borrado real (204).
set -uo pipefail
source /root/monitoreo-secrets.env
A="https://127.0.0.1/api"
TOKEN=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')
AUTH="Authorization: Bearer $TOKEN"

ID=$(curl -sk "$A/me" -H "$AUTH" | sed -E 's/.*"id":"([^"]+)".*/\1/')
echo -n "1) DELETE propia cuenta (admin) -> "; curl -sk -o /dev/null -w '%{http_code} (esperado 422)\n' -X DELETE "$A/usuarios/$ID" -H "$AUTH"

echo "2) Crear usuario de prueba…"
NEW=$(curl -sk -X POST "$A/usuarios" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"email":"zz.borrar@entidad.gov.co","nombre":"Borrar","rol":"viewer","activo":true,"password":"Borrar12345"}')
NID=$(echo "$NEW" | sed -E 's/.*"id":"([^"]+)".*/\1/')
echo "   id=$NID"
echo -n "3) DELETE usuario de prueba -> "; curl -sk -o /dev/null -w '%{http_code} (esperado 204)\n' -X DELETE "$A/usuarios/$NID" -H "$AUTH"
echo -n "4) GET usuario borrado -> "; curl -sk -o /dev/null -w '%{http_code} (esperado 404)\n' "$A/usuarios/$NID" -H "$AUTH"
