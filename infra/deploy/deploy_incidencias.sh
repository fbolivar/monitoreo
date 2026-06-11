#!/usr/bin/env bash
set -euo pipefail
cd /opt/monitoreo
git checkout -- api/composer.json frontend/src/environments/environment.ts 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== API: limpiar config + recargar php-fpm =="
( cd api && php artisan config:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm

echo "== Frontend: rebuild =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -4 )
systemctl reload nginx

echo "== Rutas de incidencias registradas =="
( cd api && php artisan route:list 2>/dev/null | grep -i "incidencias" )
