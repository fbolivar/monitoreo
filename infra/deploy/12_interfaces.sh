#!/usr/bin/env bash
# Despliega el monitoreo de interfaces SNMP (IF-MIB): migración 0004,
# activa interfaces en SW-CORE-01, reconstruye frontend y reinicia el worker.
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0004: tabla interfaces =="
$PSQL -f db/migrations/0004_interfaces.up.sql

echo "== Activar interfaces=true en SW-CORE-01 =="
$PSQL -c "UPDATE recursos SET parametros = coalesce(parametros,'{}'::jsonb) || '{\"interfaces\": true}'::jsonb WHERE nombre='SW-CORE-01' RETURNING id, nombre, intervalo_segundos, parametros;"

echo "== API: limpiar caché de rutas/config =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -4 )
systemctl reload nginx

echo "== Reiniciar worker =="
systemctl restart monitoreo-worker
echo "esperando ~3 ciclos para el delta de tráfico…"
sleep 150

echo "== Interfaces capturadas (SW-CORE-01) =="
$PSQL -c "SELECT i.if_index, i.if_name, i.oper_estado, i.in_mbps, i.out_mbps, i.util_in, i.util_out, i.speed_mbps, i.in_err, i.out_err
          FROM interfaces i JOIN recursos r ON r.id=i.recurso_id
          WHERE r.nombre='SW-CORE-01' ORDER BY i.if_index;"
echo -n "total interfaces SW-CORE-01: "
$PSQL -tAc "SELECT count(*) FROM interfaces i JOIN recursos r ON r.id=i.recurso_id WHERE r.nombre='SW-CORE-01'"

echo "== Endpoint API (con token admin) =="
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')
RID=$($PSQL -tAc "SELECT id FROM recursos WHERE nombre='SW-CORE-01'")
echo "GET /api/recursos/$RID/interfaces ->"
curl -sk "https://127.0.0.1/api/recursos/$RID/interfaces" -H "Authorization: Bearer $TOKEN" | head -c 600; echo

echo "== Logs worker =="
journalctl -u monitoreo-worker --no-pager -n 6 | tail -6
