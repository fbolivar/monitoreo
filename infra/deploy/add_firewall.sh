#!/usr/bin/env bash
# Da de alta el FortiGate-Principal vía la API. El token se pasa como argumento
# (NO se escribe en este archivo). Uso: bash add_firewall.sh '<API_TOKEN>'
set -euo pipefail
API_TOKEN="${1:?Falta el token de API como argumento}"
source /root/monitoreo-secrets.env

API=https://127.0.0.1
login() { curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])"; }

TOKEN=$(login)
H_AUTH="Authorization: Bearer $TOKEN"

TIPO=$(curl -sk "$API/api/tipos-recurso?per_page=100" -H "$H_AUTH" \
  | python3 -c "import sys,json;print(next(x['id'] for x in json.load(sys.stdin)['data'] if x['codigo']=='firewall'))")
SITIO=$(curl -sk "$API/api/sitios?per_page=100" -H "$H_AUTH" \
  | python3 -c "import sys,json;print(next(x['id'] for x in json.load(sys.stdin)['data'] if x['codigo']=='SEDE-PPAL'))")
echo "tipo_id(firewall)=$TIPO  sitio_id(SEDE-PPAL)=$SITIO"

BODY=$(python3 - "$TIPO" "$SITIO" "$API_TOKEN" <<'PY'
import json, sys
tipo, sitio, token = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
print(json.dumps({
    "tipo_id": tipo, "sitio_id": sitio, "nombre": "FortiGate-Principal",
    "hostname": "192.168.50.1:25443", "intervalo_segundos": 60, "activo": True,
    "parametros": {"verify_ssl": False, "ha_miembros_esperados": 2},
    "secretos": {"api_key": token},
}))
PY
)

echo "== Crear recurso =="
RESP=$(curl -sk -X POST "$API/api/recursos" -H "$H_AUTH" -H 'Content-Type: application/json' -d "$BODY")
echo "$RESP" | python3 -m json.tool
RID=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))")
echo "recurso_id=$RID"

echo "== Esperando 70s a que el worker lo chequee… =="
sleep 70

source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "== Estado y último chequeo =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT estado_actual, ultimo_chequeo_at FROM recursos WHERE id=$RID"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT ts, estado, latencia_ms, detalle FROM chequeos WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 1"
echo "== Métricas recientes =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT metrica, valor, unidad, ts FROM metricas WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 8"
echo "== Log del worker para este recurso =="
journalctl -u monitoreo-worker --no-pager -n 200 | grep -E "FortiGate-Principal|recurso $RID|Chequeo .*$RID" | tail -8 || echo "(sin líneas)"
