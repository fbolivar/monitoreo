#!/usr/bin/env bash
# Despliega Reportes (API+pantalla) y el Mapa de sedes. Solo API+frontend.
set -euo pipefail
source /root/monitoreo-secrets.env

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== API: limpiar caché de rutas =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Verificación endpoint disponibilidad =="
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')
echo "GET /api/reportes/disponibilidad?rango=7d ->"
curl -sk 'https://127.0.0.1/api/reportes/disponibilidad?rango=7d' \
  -H "Authorization: Bearer $TOKEN" | head -c 900; echo
echo "== SPA =="
curl -sk -o /dev/null -w 'GET / -> %{http_code}\n' https://127.0.0.1/
