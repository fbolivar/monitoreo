#!/usr/bin/env bash
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
cd /opt/monitoreo
git checkout -- api/composer.json frontend/src/environments/environment.ts 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Worker: tests + restart =="
( cd monitor && .venv/bin/pytest -q 2>&1 | tail -4 ) || echo "(pytest con fallos)"
systemctl restart monitoreo-worker

echo "== API: config + php-fpm =="
( cd api && php artisan config:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm

echo "== Frontend: rebuild =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "esperando 60s a que el worker chequee con el pool nuevo…"
sleep 60

API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

echo "== Verificaciones =="
echo -n "  estados recursos : "; psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT string_agg(nombre||'='||estado_actual,'  ') FROM recursos"
echo -n "  errores pool en worker (5 min): "; journalctl -u monitoreo-worker --since '-5 min' --no-pager | grep -ci "PoolTimeout\|pool" || true

FW=$(curl -sk "$API/api/tipos-recurso?per_page=100" -H "$H" | python3 -c "import sys,json;print(next(x['id'] for x in json.load(sys.stdin)['data'] if x['codigo']=='firewall'))")
echo -n "  DELETE tipo firewall en uso (esperado 409): "; curl -sk -o /dev/null -w '%{http_code}\n' -X DELETE "$API/api/tipos-recurso/$FW" -H "$H"
echo -n "  Admin auto-degrada a viewer (esperado 422)  : "; curl -sk -o /dev/null -w '%{http_code}\n' -X PATCH "$API/api/usuarios/00000000-0000-0000-0000-000000000001" -H "$H" -H 'Content-Type: application/json' -d '{"rol":"viewer"}'
echo -n "  GET /api/me (admin sigue admin)             : "; curl -sk "$API/api/me" -H "$H" | python3 -c "import sys,json;print(json.load(sys.stdin)['rol'])"
