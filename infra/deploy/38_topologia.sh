#!/usr/bin/env bash
# =====================================================================
# 38_topologia.sh — Topología L2 automática por LLDP [migr. 0021].
# El worker camina la LLDP-MIB de cada switch (SNMP) y registra vecinos.
# Aplica migración, reconstruye API/frontend, reinicia worker y verifica.
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

echo "== Migración 0021 (topología LLDP) =="
"${PSQL[@]}" -f db/migrations/0021_topologia.up.sql && echo "  0021 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.lldp_vecinos') AS lldp_vecinos;"

echo "== API Laravel =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker (registra el job 'topologia') =="
systemctl restart monitoreo-worker
sleep 4
journalctl -u monitoreo-worker --no-pager --since '-1min' 2>/dev/null | grep -iE "Topolog|LLDP" | tail -3 || echo "  (sin líneas LLDP aún; corre cada 10 min)"

echo "== Verificación de endpoints (sin token -> 401) =="
curl -sk -o /dev/null -w '  GET /api/topologia          -> %{http_code}\n' "$A/topologia"
curl -sk -o /dev/null -w '  GET /api/recursos/1/vecinos  -> %{http_code}\n' "$A/recursos/1/vecinos"

echo "== LISTO: topología L2 por LLDP desplegada =="
