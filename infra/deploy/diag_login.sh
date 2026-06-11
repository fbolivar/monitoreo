#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "perfil admin:"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT email, rol, activo, totp_activo, origen FROM perfiles WHERE email='admin@entidad.gov.co'"
echo "respuesta login admin:"
curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | head -c 250; echo
