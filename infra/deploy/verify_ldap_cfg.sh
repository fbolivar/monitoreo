#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
T=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')
echo "GET /api/config/ldap:"
curl -sk https://127.0.0.1/api/config/ldap -H "Authorization: Bearer $T"; echo
