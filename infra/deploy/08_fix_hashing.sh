#!/usr/bin/env bash
set -euo pipefail
source /root/monitoreo-secrets.env
cd /opt/monitoreo
git checkout -- api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

cd api
php artisan config:clear >/dev/null 2>&1 || true
systemctl reload php8.2-fpm

echo "== Verificación login =="
BODY="{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}"
TOKEN=$(curl -s -X POST http://127.0.0.1/api/auth/login -H 'Content-Type: application/json' -d "$BODY" \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))" 2>/dev/null || true)
[ -n "$TOKEN" ] && echo "  login OK (token ${#TOKEN} chars)" || echo "  LOGIN FALLÓ"
echo -n "  GET /api/me       -> "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/me -H "Authorization: Bearer $TOKEN"
echo -n "  GET /api/recursos -> "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/recursos -H "Authorization: Bearer $TOKEN"
echo "  perfil: $(curl -s http://127.0.0.1/api/me -H "Authorization: Bearer $TOKEN")"
