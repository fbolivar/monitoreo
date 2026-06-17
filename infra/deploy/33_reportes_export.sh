#!/usr/bin/env bash
# =====================================================================
# 33_reportes_export.sh — Exportación de reportes (CSV/XLSX/PDF corporativo).
# Instala extensiones PHP (gd para el logo en PDF, zip para XLSX), las libs
# (dompdf, phpspreadsheet) por composer, reconstruye API/frontend y verifica.
# =====================================================================
set -uo pipefail
A="https://127.0.0.1/api"

echo "== Extensiones PHP necesarias (gd, zip) =="
if ! php -m | grep -qi '^gd$' || ! php -m | grep -qi '^zip$'; then
  apt-get update -qq && apt-get install -y -qq php8.2-gd php8.2-zip
  systemctl reload php8.2-fpm 2>/dev/null || true
fi
echo "  gd: $(php -m | grep -qi '^gd$' && echo OK || echo FALTA) · zip: $(php -m | grep -qi '^zip$' && echo OK || echo FALTA)"

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json api/composer.lock 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Dependencias PHP (dompdf + phpspreadsheet) =="
( cd api && COMPOSER_MEMORY_LIMIT=-1 composer require dompdf/dompdf:^3.0 phpoffice/phpspreadsheet:^2.3 --no-interaction --no-progress 2>&1 | tail -6 )

echo "== Limpiar caché y recargar API =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Verificación (endpoint protegido) =="
curl -sk -o /dev/null -w '  GET /api/reportes/export/ejecutivo (sin token) -> %{http_code} (esperado 401)\n' "$A/reportes/export/ejecutivo?formato=pdf"

echo "== LISTO: exportación de reportes desplegada =="
