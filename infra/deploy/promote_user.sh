#!/usr/bin/env bash
# Cambia el rol de un usuario vía la API (queda auditado). Env: EMAIL ROL.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"

ID=$(psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT id FROM perfiles WHERE email='$EMAIL'")
if [ -z "$ID" ]; then echo "Usuario '$EMAIL' no existe."; exit 1; fi

TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

echo "PUT /api/usuarios/$ID  rol=$ROL"
curl -sk -X PUT "https://127.0.0.1/api/usuarios/$ID" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"rol\":\"$ROL\"}"; echo

echo "Estado:"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT email, rol, origen, activo FROM perfiles WHERE email='$EMAIL'"
