#!/usr/bin/env bash
# FASE 6 · Paso Servir: nginx + php-fpm. SPA en / y API (Laravel) en /api, /up.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
echo "== Instalar nginx =="
apt-get install -y -qq nginx >/dev/null
systemctl enable --now php8.2-fpm >/dev/null 2>&1
echo "nginx + php8.2-fpm OK"

echo "== Config nginx =="
cat > /etc/nginx/sites-available/monitoreo <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    # Frontend Angular (build). Existe tras el paso del frontend.
    root /opt/monitoreo/frontend/dist/frontend/browser;
    index index.html;

    client_max_body_size 10m;

    # API Laravel + health -> php-fpm (todo enruta por index.php)
    location ~ ^/(api|up)(/|$) {
        root /opt/monitoreo/api/public;
        try_files $uri @laravel;
    }
    location @laravel {
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME /opt/monitoreo/api/public/index.php;
        fastcgi_param SCRIPT_NAME /index.php;
    }

    # SPA: fallback a index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/monitoreo /etc/nginx/sites-enabled/monitoreo
rm -f /etc/nginx/sites-enabled/default

echo "== Validar y recargar =="
nginx -t
systemctl reload nginx

echo "== Verificación HTTP (localhost) =="
echo -n "GET /up           -> "; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/up
echo -n "GET /api/me       -> "; curl -s -o /dev/null -w "%{http_code} (esperado 401 sin token)\n" http://127.0.0.1/api/me
echo "Cuerpo de /api/me (debe pedir token):"
curl -s http://127.0.0.1/api/me; echo
echo -n "GET / (SPA aún sin build) -> "; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/
