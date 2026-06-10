#!/usr/bin/env bash
# FASE 6 · Actualizar despliegue desde GitHub y reconstruir el frontend.
set -euo pipefail

cd /opt/monitoreo
echo "== Sync con GitHub =="
# Descartar modificaciones locales en archivos versionados (se regeneran).
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
echo "commit actual: $(git log --oneline -1)"

echo "== Config frontend =="
grep -E "apiUrl|refreshMs" frontend/src/environments/environment.ts

echo "== Rebuild frontend =="
cd frontend
npx ng build --configuration production 2>&1 | tail -6
systemctl reload nginx

echo "== Verificación =="
curl -s -o /dev/null -w 'GET /            -> %{http_code}\n' http://127.0.0.1/
curl -s -o /dev/null -w 'GET /api/recursos -> %{http_code} (401 sin token)\n' http://127.0.0.1/api/recursos
