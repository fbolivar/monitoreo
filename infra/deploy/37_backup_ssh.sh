#!/usr/bin/env bash
# =====================================================================
# 37_backup_ssh.sh — Backup de config de switches por SSH (sin migración).
# Extiende el respaldo de config (hoy FortiGate por API) a switches por SSH:
# se conecta, deshabilita paginación y vuelca 'show running-config'. Reusa la
# tabla config_respaldos + diff + aviso + la sección "Respaldos" del detalle.
# Instala paramiko, rebuild frontend y reinicia el worker.
# =====================================================================
set -uo pipefail

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Dependencia Python (paramiko) =="
if [ -d /opt/monitoreo/monitor/.venv ]; then PIP="/opt/monitoreo/monitor/.venv/bin/pip"; else PIP="pip3"; fi
$PIP install -q 'paramiko==3.5.0' 2>&1 | tail -3
$PIP show paramiko 2>/dev/null | grep -i '^Version' || echo "  (revisar instalación de paramiko)"

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker =="
systemctl restart monitoreo-worker
sleep 4
systemctl is-active monitoreo-worker

echo "== LISTO: backup de config por SSH desplegado =="
echo "   Activar en un switch: parametros {\"backup\":{\"metodo\":\"ssh\",\"vendor\":\"dell_os9\"}}"
echo "   y secretos {\"ssh_user\":\"...\",\"ssh_password\":\"...\"} (o ssh_key PEM). Verás versiones en «Respaldos»."
