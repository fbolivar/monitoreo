#!/usr/bin/env bash
# =====================================================================
# 41_olas2_5.sh — Olas 2–5 [migr. 0025–0032]:
#   #5 runbooks · #7 cumplimiento · #8 agentes · #9 virtualización ·
#   #11 push · #12 status · #13 RUM · #14 correlación · GLPI (listo).
# Aplica migraciones, instala deps del worker (pywebpush), genera VAPID
# (push), reconstruye API/frontend, reinicia worker y verifica.
# =====================================================================
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL=(psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1)
A="https://127.0.0.1/api"
VENV=/opt/monitoreo/monitor/.venv

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null
git pull --ff-only origin main
git log --oneline -1

echo "== Migraciones 0025–0032 =="
for m in 0025_runbooks 0026_cumplimiento 0027_agentes 0028_virtualizacion 0029_push 0030_rum 0031_correlaciones 0032_glpi; do
  "${PSQL[@]}" -f "db/migrations/${m}.up.sql" >/dev/null && echo "  ${m} OK"
done

echo "== Deps worker (pywebpush para Web Push) =="
"$VENV/bin/pip" install -q pywebpush >/dev/null 2>&1 && echo "  pywebpush OK" || echo "  (pywebpush no instalado; push quedará deshabilitado)"

echo "== VAPID (Web Push) =="
PEM=/opt/monitoreo/monitor/vapid_private.pem
if [ ! -f "$PEM" ]; then
  "$VENV/bin/python" - "$PEM" <<'PY' || echo "  (no se pudo generar VAPID; push deshabilitado)"
import base64, sys
from py_vapid import Vapid01
from cryptography.hazmat.primitives import serialization
pem = sys.argv[1]
v = Vapid01(); v.generate_keys(); v.save_key(pem)
raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
pub = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
open(pem + ".pub", "w").write(pub)
print("  VAPID generado")
PY
fi
if [ -f "$PEM.pub" ]; then
  PUB=$(cat "$PEM.pub")
  # Worker .env
  grep -q '^VAPID_PRIVATE_KEY=' monitor/.env || echo "VAPID_PRIVATE_KEY=$PEM" >> monitor/.env
  grep -q '^VAPID_PUBLIC_KEY='  monitor/.env || echo "VAPID_PUBLIC_KEY=$PUB" >> monitor/.env
  # API .env (para /push/vapid -> frontend)
  grep -q '^VAPID_PUBLIC_KEY='  api/.env || echo "VAPID_PUBLIC_KEY=$PUB" >> api/.env
  echo "  clave pública VAPID: ${PUB:0:24}…"
fi

echo "== API Laravel =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker (jobs: cumplimiento, virtualización, correlación) =="
systemctl restart monitoreo-worker
sleep 4
journalctl -u monitoreo-worker --no-pager --since '-1min' 2>/dev/null | grep -iE "Cumplimiento|Virtualización|Correlación" | tail -5 || echo "  (jobs registrados; verás líneas en el próximo ciclo)"

echo "== Verificación de endpoints =="
curl -sk -o /dev/null -w '  GET  /api/status            -> %{http_code} (público)\n' "$A/status"
curl -sk -o /dev/null -w '  GET  /api/runbooks          -> %{http_code} (401 sin token)\n' "$A/runbooks"
curl -sk -o /dev/null -w '  GET  /api/correlaciones     -> %{http_code} (401 sin token)\n' "$A/correlaciones"
curl -sk -o /dev/null -w '  GET  /api/rum               -> %{http_code} (401 sin token)\n' "$A/rum"
curl -sk -o /dev/null -w '  GET  /api/push/vapid        -> %{http_code} (público)\n' "$A/push/vapid"
curl -sk -X POST -H 'Content-Type: application/json' -d '{"url":"/test","valor_ms":123}' \
     -o /dev/null -w '  POST /api/ingest/rum         -> %{http_code} (público)\n' "$A/ingest/rum"

echo "== LISTO: olas 2–5 desplegadas =="
echo "GLPI: crear un canal tipo 'glpi' (url + app_token + user_token) para abrir tickets automáticos."
echo "Agente: crea uno en /agentes, copia el token y despliega agent/simon_agent.py en el host."
