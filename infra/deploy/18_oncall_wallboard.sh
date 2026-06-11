#!/usr/bin/env bash
# Lote 1: escalado por tiempo (on-call) + Tablero NOC (wallboard).
# Migración 0008, worker (job de escalado), frontend (ruta /wallboard).
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0008 (escalada_at) =="
$PSQL -f db/migrations/0008_escalado.up.sql

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker (carga job de escalado) =="
systemctl restart monitoreo-worker
sleep 4
systemctl is-active monitoreo-worker
echo "== Jobs del scheduler (logs) =="
journalctl -u monitoreo-worker --no-pager -n 40 | grep -iE "escalad|job|scheduler" | tail -6 || true
echo "== Columna escalada_at =="
$PSQL -tAc "SELECT count(*) FROM information_schema.columns WHERE table_name='incidencias' AND column_name='escalada_at'"
echo "== /wallboard servida =="
curl -sk -o /dev/null -w '  GET /wallboard -> %{http_code}\n' https://127.0.0.1/wallboard
