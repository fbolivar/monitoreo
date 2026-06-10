#!/usr/bin/env bash
# Genera una nueva contraseña fuerte para el admin, la aplica y verifica login.
set -euo pipefail
SECRETS=/root/monitoreo-secrets.env
source "$SECRETS"
export PGPASSWORD="$DB_PASSWORD"

NEW=$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | cut -c1-16)

psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1 -q \
  -c "UPDATE perfiles SET password_hash = crypt('$NEW', gen_salt('bf')) WHERE email='admin@entidad.gov.co'"

if grep -q '^ADMIN_PASS=' "$SECRETS"; then
  sed -i "s|^ADMIN_PASS=.*|ADMIN_PASS=$NEW|" "$SECRETS"
else
  echo "ADMIN_PASS=$NEW" >> "$SECRETS"
fi

TOKEN=$(curl -s -X POST http://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
        -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$NEW\"}" \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))" 2>/dev/null || true)
[ -n "$TOKEN" ] && echo "login OK con la nueva contraseña" || echo "LOGIN FALLÓ"

echo "============================================"
echo "  NUEVA CONTRASEÑA ADMIN: $NEW"
echo "  (guardada en $SECRETS)"
echo "============================================"
