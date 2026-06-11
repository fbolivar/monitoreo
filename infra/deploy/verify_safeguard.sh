#!/usr/bin/env bash
# Verifica la salvaguarda del último admin local. Env: U PASS (admin LDAP).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
A="https://127.0.0.1/api"

T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "$U" "$PASS")" | sed -E 's/.*"token":"([^"]+)".*/\1/')

ADM=$(psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc \
  "SELECT id FROM perfiles WHERE origen='local' AND rol='admin' AND activo LIMIT 1")
echo "admin local id=$ADM"
echo -n "DELETE último admin local -> "
curl -sk -o /dev/null -w '%{http_code} (esperado 422)\n' -X DELETE "$A/usuarios/$ADM" -H "Authorization: Bearer $T"
echo -n "PATCH desactivar último admin local -> "
curl -sk -o /dev/null -w '%{http_code} (esperado 422)\n' -X PATCH "$A/usuarios/$ADM" \
  -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"activo":false}'

echo "config LDAP (debe incluir usuarios_permitidos):"
curl -sk "$A/config/ldap" -H "Authorization: Bearer $T" | sed -E 's/.*("usuarios_permitidos"[^,}]*).*/\1/'
