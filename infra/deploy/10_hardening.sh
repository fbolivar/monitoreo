#!/usr/bin/env bash
# Hardening: HTTPS (cert autofirmado), firewall ufw, y backups de la BD.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
API=/opt/monitoreo/api
IP=192.168.50.54

echo "== 1) HTTPS (certificado autofirmado) =="
mkdir -p /etc/ssl/monitoreo
if [ ! -f /etc/ssl/monitoreo/cert.pem ]; then
  openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout /etc/ssl/monitoreo/key.pem -out /etc/ssl/monitoreo/cert.pem \
    -subj "/CN=${IP}" -addext "subjectAltName=IP:${IP}" 2>/dev/null
  chmod 600 /etc/ssl/monitoreo/key.pem
fi

cat > /etc/nginx/sites-available/monitoreo <<'NGINX'
# HTTP -> redirige a HTTPS
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
# HTTPS
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;

    ssl_certificate     /etc/ssl/monitoreo/cert.pem;
    ssl_certificate_key /etc/ssl/monitoreo/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    root /opt/monitoreo/frontend/dist/frontend/browser;
    index index.html;
    client_max_body_size 10m;

    location ~ ^/(api|up)(/|$) {
        root /opt/monitoreo/api/public;
        try_files $uri @laravel;
    }
    location @laravel {
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME /opt/monitoreo/api/public/index.php;
        fastcgi_param SCRIPT_NAME /index.php;
        fastcgi_param HTTPS on;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

# APP_URL a https
if grep -q '^APP_URL=' "$API/.env"; then
  sed -i "s|^APP_URL=.*|APP_URL=https://${IP}|" "$API/.env"
fi
( cd "$API" && php artisan config:clear >/dev/null 2>&1 || true )

nginx -t
systemctl reload nginx
echo "  HTTPS OK"

echo "== 2) Firewall ufw =="
apt-get install -y -qq ufw >/dev/null
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status verbose | sed -n '1,12p'

echo "== 3) Backups de la BD =="
cat > /usr/local/bin/monitoreo-backup.sh <<'BACKUP'
#!/usr/bin/env bash
set -euo pipefail
source /root/monitoreo-secrets.env
DIR=/var/backups/monitoreo
mkdir -p "$DIR"
export PGPASSWORD="$DB_PASSWORD"
TS=$(date +%Y%m%d_%H%M%S)
pg_dump -h 127.0.0.1 -U monitoreo -d monitoreo -Fc -f "$DIR/monitoreo_$TS.dump"
# Rotación: conservar las 14 más recientes
ls -1t "$DIR"/monitoreo_*.dump 2>/dev/null | tail -n +15 | xargs -r rm -f
BACKUP
chmod 700 /usr/local/bin/monitoreo-backup.sh

cat > /etc/cron.d/monitoreo-backup <<'CRON'
# Backup diario de la BD de monitoreo a las 02:30
30 2 * * * root /usr/local/bin/monitoreo-backup.sh >> /var/log/monitoreo-backup.log 2>&1
CRON
chmod 644 /etc/cron.d/monitoreo-backup

echo "  ejecutando un backup de prueba…"
/usr/local/bin/monitoreo-backup.sh
ls -lh /var/backups/monitoreo/ | tail -3

echo "== Verificación HTTPS =="
curl -sk -o /dev/null -w 'GET https://127.0.0.1/        -> %{http_code}\n' https://127.0.0.1/
curl -sk -o /dev/null -w 'GET https://127.0.0.1/api/me  -> %{http_code} (401 sin token)\n' https://127.0.0.1/api/me
curl -s  -o /dev/null -w 'GET http://127.0.0.1/ (->301) -> %{http_code}\n' http://127.0.0.1/
