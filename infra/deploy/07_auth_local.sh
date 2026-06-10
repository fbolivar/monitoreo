#!/usr/bin/env bash
# FASE 6 · Auth local: migración password_hash, AUTH_JWT_SECRET, password admin,
# autoloader, rebuild frontend y verificación del login.
set -euo pipefail

REPO=/opt/monitoreo; API="$REPO/api"; FE="$REPO/frontend"
SECRETS=/root/monitoreo-secrets.env
source "$SECRETS"                 # DB_PASSWORD, APP_CRYPTO_KEY
export PGPASSWORD="$DB_PASSWORD"
export COMPOSER_ALLOW_SUPERUSER=1

echo "== Sync repo =="
cd "$REPO"
git checkout -- api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

# Claves (reusar si ya existen)
AUTH_JWT_SECRET=$(grep -E '^AUTH_JWT_SECRET=' "$SECRETS" 2>/dev/null | cut -d= -f2- || true)
[ -n "${AUTH_JWT_SECRET:-}" ] || AUTH_JWT_SECRET=$(openssl rand -hex 32)
ADMIN_PASS=$(grep -E '^ADMIN_PASS=' "$SECRETS" 2>/dev/null | cut -d= -f2- || true)
[ -n "${ADMIN_PASS:-}" ] || ADMIN_PASS=$(openssl rand -hex 9)

echo "== Migración 0003 + password admin =="
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1 -q"
$PSQL -f "$REPO/db/migrations/0003_auth_local.up.sql"
$PSQL -v admin_pass="$ADMIN_PASS" -f "$REPO/db/seeds/0005_password_admin.sql"
echo "  columna + hash admin OK"

echo "== .env API (AUTH_JWT_SECRET) =="
set_env(){ local k="$1" v="$2"; if grep -q "^${k}=" "$API/.env"; then sed -i "s|^${k}=.*|${k}=${v}|" "$API/.env"; else echo "${k}=${v}" >> "$API/.env"; fi; }
set_env AUTH_JWT_SECRET "$AUTH_JWT_SECRET"
set_env AUTH_JWT_TTL 43200

echo "== Autoloader + limpiar config =="
cd "$API"
composer dump-autoload -o --no-interaction 2>&1 | tail -2
php artisan config:clear >/dev/null 2>&1 || true
chown -R www-data:www-data "$API/storage" "$API/bootstrap/cache"

echo "== Rebuild frontend =="
cd "$FE"
npx ng build --configuration production 2>&1 | tail -4
systemctl reload nginx

# Guardar claves
umask 077
grep -q '^AUTH_JWT_SECRET=' "$SECRETS" || echo "AUTH_JWT_SECRET=$AUTH_JWT_SECRET" >> "$SECRETS"
grep -q '^ADMIN_PASS=' "$SECRETS" || echo "ADMIN_PASS=$ADMIN_PASS" >> "$SECRETS"

echo "== Verificación login =="
BODY="{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}"
TOKEN=$(curl -s -X POST http://127.0.0.1/api/auth/login -H 'Content-Type: application/json' -d "$BODY" \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))" 2>/dev/null || true)
if [ -n "$TOKEN" ]; then echo "  login OK (token ${#TOKEN} chars)"; else echo "  LOGIN FALLÓ"; fi
echo -n "  GET /api/me       -> "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/me -H "Authorization: Bearer $TOKEN"
echo -n "  GET /api/recursos -> "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/recursos -H "Authorization: Bearer $TOKEN"
echo "  perfil: $(curl -s http://127.0.0.1/api/me -H "Authorization: Bearer $TOKEN")"

echo
echo "================ CREDENCIALES DE ACCESO ================"
echo "  URL:      http://192.168.50.54/"
echo "  Usuario:  admin@entidad.gov.co"
echo "  Password: $ADMIN_PASS"
echo "======================================================="
