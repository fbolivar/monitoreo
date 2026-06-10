#!/usr/bin/env bash
# FASE 6 · Paso API: PHP 8.2 + Composer + dependencias + .env + verificación.
set -euo pipefail

REPO=/opt/monitoreo
API="$REPO/api"
# DB_PASSWORD y APP_CRYPTO_KEY generadas en el paso BD.
source /root/monitoreo-secrets.env

export DEBIAN_FRONTEND=noninteractive
export COMPOSER_ALLOW_SUPERUSER=1

echo "== Instalar PHP + extensiones =="
apt-get update -qq
apt-get install -y -qq php-cli php-fpm php-pgsql php-mbstring php-xml php-curl \
  php-bcmath php-zip php-intl unzip >/dev/null
php -v | head -1

echo "== Composer =="
if ! command -v composer >/dev/null; then
  php -r "copy('https://getcomposer.org/installer','/tmp/composer-setup.php');"
  php /tmp/composer-setup.php --install-dir=/usr/local/bin --filename=composer --quiet
  php -r "@unlink('/tmp/composer-setup.php');"
fi
composer --version

echo "== composer install =="
cd "$API"
# El mirror (2026) marca con advisories todo el rango de Laravel 11.x / php-jwt 6.x
# disponible; no hay versión limpia que satisfaga las restricciones, así que se
# desactiva el bloqueo SOLO en este proyecto. TODO: subir a release parcheada.
composer config policy.advisories.block false 2>/dev/null || true
composer install --no-dev --no-interaction --optimize-autoloader --no-progress 2>&1 | tail -6

echo "== .env =="
[ -f "$API/.env" ] || cp "$API/.env.example" "$API/.env"
set_env() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "$API/.env"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "$API/.env"
  else
    echo "${k}=${v}" >> "$API/.env"
  fi
}
set_env APP_ENV production
set_env APP_DEBUG false
set_env APP_URL http://192.168.50.54
set_env DB_CONNECTION pgsql
set_env DB_HOST 127.0.0.1
set_env DB_PORT 5432
set_env DB_DATABASE monitoreo
set_env DB_USERNAME monitoreo
set_env DB_PASSWORD "$DB_PASSWORD"
set_env DB_SSLMODE prefer
set_env APP_CRYPTO_KEY "$APP_CRYPTO_KEY"
grep -q '^SUPABASE_JWT_SECRET=' "$API/.env" || echo 'SUPABASE_JWT_SECRET=PENDIENTE_DEFINIR' >> "$API/.env"

php artisan key:generate --force
php artisan config:clear >/dev/null 2>&1 || true

echo "== Permisos (php-fpm corre como www-data) =="
chown -R www-data:www-data "$API/storage" "$API/bootstrap/cache"
chmod -R ug+rwX "$API/storage" "$API/bootstrap/cache"

echo "== Verificación: php artisan route:list =="
php artisan route:list 2>&1 | sed -n '1,45p'

echo "== Verificación: conexión a la BD desde Laravel =="
php artisan tinker --execute="echo 'recursos=' . DB::table('recursos')->count() . ' incidencias=' . DB::table('incidencias')->count() . PHP_EOL;" 2>&1 | tail -2
