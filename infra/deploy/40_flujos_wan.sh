#!/usr/bin/env bash
# =====================================================================
# 40_flujos_wan.sh — Ola de visibilidad de red [migr. 0024]:
#  (1) NetFlow/IPFIX: colector simon-netflow (UDP/2055) -> tabla flujos.
#  (4) Calidad WAN activa: job medir_calidad_wan -> tabla wan_calidad (MOS).
# Aplica migración, reconstruye API/frontend, instala el servicio, abre ufw,
# reinicia worker y verifica.
# =====================================================================
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL=(psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1)
A="https://127.0.0.1/api"

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0024 (flujos + wan_calidad) =="
"${PSQL[@]}" -f db/migrations/0024_flujos_wan.up.sql && echo "  0024 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.flujos') AS flujos, to_regclass('public.wan_calidad') AS wan_calidad;"

echo "== iperf3 (para throughput WAN; opcional) =="
command -v iperf3 >/dev/null 2>&1 || apt-get install -y iperf3 >/dev/null 2>&1 || true
printf "  iperf3: "; command -v iperf3 || echo "(no instalado; la calidad WAN funciona sin throughput)"

echo "== API Laravel =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Servicio simon-netflow (UDP/2055) =="
cp infra/deploy/simon-netflow.service /etc/systemd/system/simon-netflow.service
systemctl daemon-reload
systemctl enable --now simon-netflow >/dev/null 2>&1 || systemctl restart simon-netflow
ufw allow 2055/udp >/dev/null 2>&1 || true
printf "  simon-netflow: "; systemctl is-active simon-netflow

echo "== Reiniciar worker (registra el job 'wan-calidad') =="
systemctl restart monitoreo-worker
sleep 4
journalctl -u monitoreo-worker --no-pager --since '-1min' 2>/dev/null | grep -iE "Calidad WAN|wan-calidad" | tail -3 || echo "  (sin líneas WAN aún; corre cada 5 min y requiere recursos opt-in)"

echo "== Verificación de endpoints (sin token -> 401) =="
curl -sk -o /dev/null -w '  GET /api/flujos                 -> %{http_code}\n' "$A/flujos"
curl -sk -o /dev/null -w '  GET /api/recursos/1/wan-calidad  -> %{http_code}\n' "$A/recursos/1/wan-calidad"

echo "== LISTO =="
echo "Para recibir flujos: en el FortiGate -> config system netflow / set collector-ip <IP_SIMON> / set collector-port 2055."
echo "Para medir calidad WAN: en un recurso WAN/Starlink agrega parametros.wan_calidad = {\"iperf_host\":\"<srv iperf3>\"} (o {} para solo ICMP)."
