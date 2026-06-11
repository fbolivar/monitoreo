#!/usr/bin/env bash
# Configura el canal email (Google Workspace), activa notificaciones y envía
# un correo de prueba. La App Password se pasa como argumento (no se guarda aquí).
# Uso: bash config_email.sh '<app password>'
set -euo pipefail
APP_PASS="${1:?Falta la App Password como argumento}"
APP_PASS="${APP_PASS// /}"   # quitar espacios de la App Password
source /root/monitoreo-secrets.env

API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

echo "== 1) Crear canal email =="
BODY=$(python3 - "$APP_PASS" <<'PY'
import json, sys
pw = sys.argv[1]
correo = "redes.seguridad@parquesnacionales.gov.co"
print(json.dumps({
    "tipo": "email", "nombre": "Correo NOC", "activo": True,
    "config": {
        "smtp_host": "smtp.gmail.com", "smtp_port": 587,
        "from": correo, "destinatarios": [correo], "min_severidad": "warning",
    },
    "secretos": {"smtp_user": correo, "smtp_pass": pw},
}))
PY
)
curl -sk -X POST "$API/api/canales-notificacion" -H "$H" -H 'Content-Type: application/json' -d "$BODY" \
  | python3 -m json.tool

echo "== 2) Activar notificaciones en el worker =="
sed -i 's/^NOTIF_ENABLED=.*/NOTIF_ENABLED=true/' /opt/monitoreo/monitor/.env
grep '^NOTIF_ENABLED=' /opt/monitoreo/monitor/.env
systemctl restart monitoreo-worker
sleep 4
echo -n "worker: "; systemctl is-active monitoreo-worker

echo "== 3) Correo de prueba =="
cd /opt/monitoreo/monitor
.venv/bin/python <<'PY'
from monitor.config import cargar_settings
from monitor.db import Database
from monitor import repository as repo
from monitor.notificaciones import senders

s = cargar_settings()
db = Database(s)
canales = [c for c in repo.canales_activos(db, s.app_crypto_key) if c.tipo == "email"]
if not canales:
    print("  NO HAY CANAL EMAIL ACTIVO")
else:
    c = canales[0]
    msg = {
        "asunto": "[PRUEBA] Monitoreo TI — correo operativo",
        "texto": "Correo de prueba del Sistema de Monitoreo de Disponibilidad de TI.\n"
                 "Si recibes este mensaje, las notificaciones por email estan activas.",
        "evento": "prueba", "recurso": "-", "severidad": "info",
    }
    ok, err, dest = senders.enviar(c, msg)
    print(f"  RESULTADO -> ok={ok}  destino={dest}  error={err}")
db.close()
PY
