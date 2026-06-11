#!/usr/bin/env bash
# Despliega el cambio (login por usuario corto) y reconfigura el patrón de bind
# para que agregue el sufijo de dominio: {user}@pnnc.local. Limpia el perfil de
# prueba con UPN completo para evitar duplicados.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload php8.2-fpm 2>/dev/null || true
systemctl reload nginx

TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

echo "Reconfigurando bind_pattern = {user}@pnnc.local …"
curl -sk -o /dev/null -w '  PUT -> %{http_code}\n' -X PUT https://127.0.0.1/api/config/ldap \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"enabled":true,"host":"ldaps://192.168.50.2","port":636,"use_tls":false,"bind_pattern":"{user}@pnnc.local","rol_default":"viewer"}'

echo "Limpiando perfil de prueba con UPN completo (si existe)…"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "DELETE FROM perfiles WHERE email='fernando.bolivar@pnnc.local'"

echo "Config LDAP final:"
curl -sk https://127.0.0.1/api/config/ldap -H "Authorization: Bearer $TOKEN"; echo
