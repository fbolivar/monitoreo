#!/usr/bin/env bash
# Despliega el sender de Teams (provisto) y el tipo de canal 'teams' (API+front).
# Telegram ya estaba implementado; solo se reconstruye. Sin migración.
set -euo pipefail
source /root/monitoreo-secrets.env

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== API: limpiar caché =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker (carga sender de Teams) =="
systemctl restart monitoreo-worker
sleep 3
systemctl is-active monitoreo-worker
echo "OK — Telegram operativo (configurar canal); Teams provisto (sin configurar)."
