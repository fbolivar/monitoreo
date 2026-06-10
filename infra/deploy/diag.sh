#!/usr/bin/env bash
echo "== php-fpm activo =="; systemctl is-active php8.2-fpm
echo "== socket =="; ls -l /run/php/ 2>&1
echo "== index.php =="; ls -l /opt/monitoreo/api/public/index.php
echo "== frontend dist =="; ls -ld /opt/monitoreo/frontend/dist 2>&1
echo "== HTTP /up =="; curl -s -o /dev/null -w 'code=%{http_code}\n' http://127.0.0.1/up
echo "== /up cabeceras =="; curl -sI http://127.0.0.1/up
echo "== nginx error log (cola) =="; tail -n 15 /var/log/nginx/error.log
echo "== www-data puede leer index.php? =="; sudo -u www-data test -r /opt/monitoreo/api/public/index.php && echo "SI" || echo "NO"
echo "== perms cadena =="; namei -l /opt/monitoreo/api/public/index.php
