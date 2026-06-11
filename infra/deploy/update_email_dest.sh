#!/usr/bin/env bash
# Actualiza los destinatarios del canal email (sin tocar la App Password).
set -euo pipefail
source /root/monitoreo-secrets.env
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

# id del canal email
CID=$(curl -sk "$API/api/canales-notificacion?per_page=50" -H "$H" \
  | python3 -c "import sys,json;print(next(x['id'] for x in json.load(sys.stdin)['data'] if x['tipo']=='email'))")
echo "canal email id=$CID"

BODY=$(python3 <<'PY'
import json
correo_oficial = "redes.seguridad@parquesnacionales.gov.co"
print(json.dumps({
    "tipo": "email", "nombre": "Correo NOC", "activo": True,
    "config": {
        "smtp_host": "smtp.gmail.com", "smtp_port": 587,
        "from": correo_oficial,
        "destinatarios": ["fbolivarb@gmail.com", correo_oficial],
        "min_severidad": "warning",
    },
}))
PY
)
echo "== Actualizando destinatarios (App Password se conserva) =="
curl -sk -X PUT "$API/api/canales-notificacion/$CID" -H "$H" -H 'Content-Type: application/json' -d "$BODY" \
  | python3 -m json.tool
