#!/usr/bin/env bash
# =====================================================================
# 34_descubrimiento.sh — Auto-descubrimiento de red [migr. 0019].
# Aplica la migración (tablas descubrimiento_escaneos/_candidatos),
# reconstruye API/frontend, reinicia el worker (nuevo job de barrido) y
# verifica los endpoints y el registro del job en el scheduler.
# =====================================================================
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL=(psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1)
A="https://127.0.0.1/api"

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0019 (descubrimiento) =="
"${PSQL[@]}" -f db/migrations/0019_descubrimiento.up.sql && echo "  0019 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.descubrimiento_escaneos') AS escaneos, to_regclass('public.descubrimiento_candidatos') AS candidatos;"

echo "== API Laravel (CRUD descubrimiento) =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker (registra el job 'descubrimiento') =="
systemctl restart monitoreo-worker
sleep 4
journalctl -u monitoreo-worker --no-pager -n 12 2>/dev/null | grep -i "descubr\|auto-descub\|scheduler\|iniciado" || true

echo "== Verificación de endpoints (sin token -> 401) =="
curl -sk -o /dev/null -w '  GET  /api/descubrimiento        -> %{http_code}\n' "$A/descubrimiento"
curl -sk -o /dev/null -w '  POST /api/descubrimiento        -> %{http_code}\n' -X POST "$A/descubrimiento"

echo "== LISTO: auto-descubrimiento desplegado =="
echo "   Prueba: en la UI (admin/operador) ve a 'Descubrimiento', escanea una /24 con community y revisa candidatos."
