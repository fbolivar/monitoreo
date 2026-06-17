#!/usr/bin/env bash
# =====================================================================
# 35_hardware.sh — Monitoreo de hardware físico (Redfish + fallback IPMI) [migr. 0020].
# Aplica la migración, instala ipmitool (para el fallback), reconstruye API/frontend,
# reinicia el worker (job 'hardware') y verifica endpoints + registro del job.
# =====================================================================
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL=(psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1)
A="https://127.0.0.1/api"

echo "== ipmitool (fallback IPMI) =="
command -v ipmitool >/dev/null 2>&1 || apt-get install -y -qq ipmitool
echo "  ipmitool: $(command -v ipmitool || echo 'NO instalado')"

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0020 (hardware) =="
"${PSQL[@]}" -f db/migrations/0020_hardware.up.sql && echo "  0020 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.hardware_inventario') AS inventario, to_regclass('public.hardware_componentes') AS componentes;"

echo "== API Laravel =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker (registra el job 'hardware') =="
systemctl restart monitoreo-worker
sleep 4
journalctl -u monitoreo-worker --no-pager -n 30 2>/dev/null | grep -i "hardware" | tail -3 || echo "  (sin líneas de hardware aún)"

echo "== Verificación de endpoint (sin token -> 401) =="
curl -sk -o /dev/null -w '  GET /api/recursos/1/hardware -> %{http_code}\n' "$A/recursos/1/hardware"

echo "== LISTO: monitoreo de hardware desplegado =="
echo "   Para activarlo en un servidor: en Recursos, parametros.hardware = {\"protocolo\":\"auto\"}"
echo "   y secretos {bmc_user, bmc_password} apuntando al iDRAC/iLO/BMC (o bmc_host distinto)."
