#!/usr/bin/env bash
source /root/monitoreo-secrets.env
echo "== Login HTTPS con nueva contraseña admin =="
TOKEN=$(curl -sk -X POST https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
        -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))" 2>/dev/null || true)
[ -n "$TOKEN" ] && echo "  login HTTPS OK (token ${#TOKEN} chars)" || echo "  LOGIN FALLÓ"
echo -n "  GET https /api/recursos -> "; curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/api/recursos -H "Authorization: Bearer $TOKEN"
echo -n "  GET https /api/usuarios -> "; curl -sk -o /dev/null -w '%{http_code} (admin)\n' https://127.0.0.1/api/usuarios -H "Authorization: Bearer $TOKEN"
echo "== Servicios =="
echo -n "  worker: "; systemctl is-active monitoreo-worker
echo -n "  nginx:  "; systemctl is-active nginx
echo -n "  php-fpm:"; systemctl is-active php8.2-fpm
echo -n "  ufw:    "; ufw status | head -1
echo "== Datos del worker (vivo) =="
export PGPASSWORD="$DB_PASSWORD"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT 'chequeos='||count(*) FROM chequeos"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT estado_actual, count(*) FROM recursos GROUP BY estado_actual ORDER BY 2 DESC"
