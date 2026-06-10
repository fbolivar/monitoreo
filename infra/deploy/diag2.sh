#!/usr/bin/env bash
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "== AUTH_JWT_SECRET en .env =="
grep -E '^AUTH_JWT' /opt/monitoreo/api/.env || echo "(ausente)"
echo "== hash admin en BD =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT email, left(password_hash,7) AS pref, length(password_hash) AS len, activo FROM perfiles WHERE email='admin@entidad.gov.co'"
echo "== login (respuesta cruda) =="
curl -s -i -X POST http://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | head -25
echo
echo "== ultimo error Laravel =="
tail -n 25 /opt/monitoreo/api/storage/logs/laravel.log 2>/dev/null || echo "(sin log)"
