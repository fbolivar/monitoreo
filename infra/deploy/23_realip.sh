#!/usr/bin/env bash
# Instala la config nginx con real_ip + log de diagnóstico de IP de origen.
set -uo pipefail
cd /opt/monitoreo
git pull --ff-only origin main >/dev/null 2>&1 || true

cp -a /etc/nginx/sites-enabled/monitoreo "/etc/nginx/sites-available/monitoreo.bak" 2>/dev/null || true
# sites-enabled/monitoreo suele ser symlink a sites-available/monitoreo
DEST=$(readlink -f /etc/nginx/sites-enabled/monitoreo)
cp infra/deploy/nginx-monitoreo.conf "$DEST"

echo "== nginx -t =="
nginx -t
echo "== reload =="
systemctl reload nginx && echo "  nginx recargado OK"

echo "== Estado: real_ip activo. Pide al usuario que recargue SIMON en el navegador =="
echo "   y luego revisa: tail -f /var/log/nginx/access.log | grep recursos"
