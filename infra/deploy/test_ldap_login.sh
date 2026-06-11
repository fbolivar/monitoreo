#!/usr/bin/env bash
# Prueba el LOGIN real vía LDAP por el endpoint. Credenciales por env: USERUPN PASS.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"

RESP=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "$USERUPN" "$PASS")")
echo "$RESP" | sed -E 's/"token":"[^"]+"/"token":"<...>"/' | head -c 400; echo
echo "$RESP" | grep -q '"token"' && echo "  -> LOGIN LDAP OK" || echo "  -> LOGIN LDAP FALLÓ"

echo "Perfil creado:"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT email, rol, origen, activo FROM perfiles WHERE email='$USERUPN'"
