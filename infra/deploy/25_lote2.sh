#!/usr/bin/env bash
# Lote 2: respaldo de configuración (FortiGate). Migración 0012, API, frontend,
# y fuerza un respaldo ahora para verificar. Env: U/PASS (admin para la API).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0012 (config_respaldos) =="
$PSQL -f db/migrations/0012_config_respaldos.up.sql

echo "== API + frontend =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker =="
systemctl restart monitoreo-worker; sleep 4; printf "  worker: "; systemctl is-active monitoreo-worker

echo "== Forzar un respaldo ahora (FortiGate real) =="
( cd /opt/monitoreo/monitor && .venv/bin/python -c "from monitor.config import cargar_settings; from monitor.db import Database; from monitor.runner import respaldar_configuraciones; s=cargar_settings(); db=Database(s); respaldar_configuraciones(db,s); db.close(); print('respaldo ejecutado')" 2>&1 | tail -4 )

echo "== config_respaldos =="
$PSQL -c "SELECT cr.id, r.nombre, cr.ts, cr.bytes, cr.cambio FROM config_respaldos cr JOIN recursos r ON r.id=cr.recurso_id ORDER BY cr.ts DESC LIMIT 5"

echo "== API: respaldos del firewall =="
T=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "${U:-}" "${PASS:-}")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
FW=$($PSQL -tAc "SELECT id FROM recursos WHERE tipo_id=(SELECT id FROM tipos_recurso WHERE codigo='firewall') ORDER BY id LIMIT 1")
echo "GET /api/recursos/$FW/respaldos ->"
curl -sk "https://127.0.0.1/api/recursos/$FW/respaldos" -H "Authorization: Bearer $T" | head -c 300; echo
