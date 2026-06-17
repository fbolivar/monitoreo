#!/usr/bin/env bash
# =====================================================================
# 39_hw_incidencias_lldp_mgmt.sh — Incidencias de hardware por componente
# [migr. 0022] + topología por dirección de gestión LLDP [migr. 0023].
# =====================================================================
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL=(psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1)

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migraciones 0022 (incidencias.componente) + 0023 (lldp.remote_mgmt) =="
"${PSQL[@]}" -f db/migrations/0022_incidencias_componente.up.sql && echo "  0022 OK"
"${PSQL[@]}" -f db/migrations/0023_lldp_mgmt.up.sql && echo "  0023 OK"
"${PSQL[@]}" -c "SELECT column_name FROM information_schema.columns WHERE table_name='incidencias' AND column_name='componente' UNION ALL SELECT column_name FROM information_schema.columns WHERE table_name='lldp_vecinos' AND column_name='remote_mgmt';"

echo "== API + frontend + worker =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx
systemctl restart monitoreo-worker
sleep 3
echo "  worker: $(systemctl is-active monitoreo-worker)"

echo "== LISTO =="
