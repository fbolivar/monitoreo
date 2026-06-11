#!/usr/bin/env bash
# Lote 2: SNMP traps (servicio simon-traps) + SSO LDAP (env-gated) + 2FA TOTP.
# Migraciones 0009/0010, php-ldap, servicio de traps, frontend. Verifica todo.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
VENV=/opt/monitoreo/monitor/.venv/bin/python

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migraciones 0009 (traps) y 0010 (2fa/ldap) =="
$PSQL -f db/migrations/0009_traps.up.sql
$PSQL -f db/migrations/0010_auth_2fa_ldap.up.sql

echo "== php-ldap + net-snmp (cliente para prueba) =="
DEBIAN_FRONTEND=noninteractive apt-get install -y php8.2-ldap snmp >/dev/null 2>&1 || true

echo "== API: limpiar caché =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || systemctl restart php8.2-fpm

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Servicio simon-traps (UDP/162) =="
cp infra/deploy/simon-traps.service /etc/systemd/system/simon-traps.service
systemctl daemon-reload
ufw allow 162/udp >/dev/null 2>&1 || true
systemctl enable --now simon-traps >/dev/null 2>&1 || systemctl restart simon-traps
sleep 4
printf "  simon-traps: "; systemctl is-active simon-traps

echo "== Prueba: enviar un trap linkDown a 127.0.0.1 =="
if command -v snmptrap >/dev/null 2>&1; then
  snmptrap -v2c -c public 127.0.0.1:162 '' 1.3.6.1.6.3.1.1.5.3 \
    1.3.6.1.2.1.2.2.1.1 i 7 2>/dev/null || echo "  (snmptrap error)"
  sleep 2
  $PSQL -c "SELECT ts, source_ip, nombre, severidad FROM traps ORDER BY ts DESC LIMIT 3"
else
  echo "  snmptrap no disponible; envía un trap desde un equipo para probar."
fi

echo "== Prueba 2FA (iniciar + activar + login) =="
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')
SECRET=$(curl -sk -X POST https://127.0.0.1/api/2fa/iniciar -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{}' | sed -E 's/.*"secret":"([^"]+)".*/\1/')
echo "  secret 2FA generado: ${SECRET:0:6}…"
CODE=$($VENV infra/deploy/gen_totp.py "$SECRET")
echo "  código TOTP: $CODE"
curl -sk -X POST https://127.0.0.1/api/2fa/activar -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"codigo\":\"$CODE\"}"; echo
echo "  login SIN código (debe pedir 2FA):"
curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | head -c 120; echo
echo "  login CON código:"
CODE2=$($VENV infra/deploy/gen_totp.py "$SECRET")
curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\",\"codigo\":\"$CODE2\"}" \
  | grep -q '"token"' && echo "  -> login con 2FA OK" || echo "  -> login con 2FA FALLÓ"
echo "  desactivando 2FA del admin (limpieza)…"
CODE3=$($VENV infra/deploy/gen_totp.py "$SECRET")
curl -sk -X POST https://127.0.0.1/api/2fa/desactivar -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"codigo\":\"$CODE3\"}"; echo
