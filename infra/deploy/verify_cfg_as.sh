#!/usr/bin/env bash
# Verifica config LDAP autenticando con un usuario dado. Env: U PASS.
set -uo pipefail
T=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "$U" "$PASS")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
echo "GET /api/config/ldap:"
curl -sk https://127.0.0.1/api/config/ldap -H "Authorization: Bearer $T"; echo
