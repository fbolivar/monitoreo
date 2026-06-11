#!/usr/bin/env bash
# Módulo de configuración LDAP en la UI: migración 0011 (app_config), API y frontend.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0011 (app_config) =="
$PSQL -f db/migrations/0011_app_config.up.sql

echo "== API: limpiar caché =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Verificación de endpoints (admin) =="
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

echo "GET /api/config/ldap ->"
curl -sk https://127.0.0.1/api/config/ldap -H "Authorization: Bearer $TOKEN"; echo

echo "PUT /api/config/ldap (guardar, deshabilitado) ->"
curl -sk -o /dev/null -w '  %{http_code}\n' -X PUT https://127.0.0.1/api/config/ldap \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"enabled":false,"host":"ldap://dc.ejemplo.local","port":389,"use_tls":false,"bind_pattern":"{user}@ejemplo.local","rol_default":"viewer"}'

echo "GET de nuevo (persistido) ->"
curl -sk https://127.0.0.1/api/config/ldap -H "Authorization: Bearer $TOKEN"; echo

echo "POST /api/config/ldap/probar (host inexistente, debe dar ok:false) ->"
curl -sk -X POST https://127.0.0.1/api/config/ldap/probar -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"host":"ldap://127.0.0.1","port":389,"bind_pattern":"{user}","test_usuario":"x","test_password":"y"}'; echo

echo "== app_config =="
$PSQL -c "SELECT clave, valor FROM app_config"
