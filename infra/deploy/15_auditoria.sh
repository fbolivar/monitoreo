#!/usr/bin/env bash
# Despliega la bitácora de auditoría: migración 0006, API y frontend.
# Verifica: tabla, captura de login y de crear/eliminar (sitio de prueba) con actor.
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0006: tabla auditoria =="
$PSQL -f db/migrations/0006_auditoria.up.sql

echo "== API: limpiar caché =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Login (genera evento 'login') =="
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')
[ -n "$TOKEN" ] && echo "  login OK" || echo "  LOGIN FALLÓ"

echo "== Crear sitio de prueba (genera 'crear') =="
SID=$(curl -sk -X POST https://127.0.0.1/api/sitios -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"codigo":"ZZ-AUDIT","nombre":"Prueba auditoria"}' | sed -E 's/.*"id":([0-9]+).*/\1/')
echo "  sitio creado id=$SID"

echo "== Eliminar sitio de prueba (genera 'eliminar') =="
curl -sk -o /dev/null -w '  DELETE -> %{http_code}\n' -X DELETE "https://127.0.0.1/api/sitios/$SID" \
  -H "Authorization: Bearer $TOKEN"

echo "== Endpoint /api/auditoria (admin) — últimas entradas =="
curl -sk 'https://127.0.0.1/api/auditoria?per_page=6' -H "Authorization: Bearer $TOKEN" | head -c 1200; echo

echo "== Tabla auditoria (resumen) =="
$PSQL -c "SELECT ts, actor_email, accion, entidad, descripcion FROM auditoria ORDER BY ts DESC LIMIT 8"
echo -n "total auditoria: "; $PSQL -tAc "SELECT count(*) FROM auditoria"
