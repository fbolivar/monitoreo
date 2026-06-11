#!/usr/bin/env bash
# Prueba la conexión LDAP contra un AD real. Credenciales por variables de entorno
# (NO se guardan en el repo): HOST PORT BINDPAT TEST_USER TEST_PASS.
set -uo pipefail
source /root/monitoreo-secrets.env
cd /opt/monitoreo
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

BODY=$(printf '{"host":"%s","port":%s,"use_tls":false,"bind_pattern":"%s","test_usuario":"%s","test_password":"%s"}' \
  "$HOST" "$PORT" "$BINDPAT" "$TEST_USER" "$TEST_PASS")

echo "Probando LDAP  $HOST:$PORT  patrón='$BINDPAT'  usuario='$TEST_USER'"
curl -sk -X POST https://127.0.0.1/api/config/ldap/probar -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "$BODY"; echo
