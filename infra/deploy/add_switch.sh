#!/usr/bin/env bash
# Da de alta SW-CORE-01 (Dell OS9) por SNMP v2c. Community como argumento.
# Uso: bash add_switch.sh '<community>'
set -euo pipefail
COMMUNITY="${1:?Falta la community}"
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

TIPO=$(curl -sk "$API/api/tipos-recurso?per_page=100" -H "$H" \
  | python3 -c "import sys,json;print(next(x['id'] for x in json.load(sys.stdin)['data'] if x['codigo']=='switch_lan'))")
SITIO=$(curl -sk "$API/api/sitios?per_page=100" -H "$H" \
  | python3 -c "import sys,json;print(next(x['id'] for x in json.load(sys.stdin)['data'] if x['codigo']=='SEDE-PPAL'))")
echo "tipo_id(switch_lan)=$TIPO  sitio_id(SEDE-PPAL)=$SITIO"

BODY=$(python3 - "$TIPO" "$SITIO" "$COMMUNITY" <<'PY'
import json, sys
tipo, sitio, comm = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
print(json.dumps({
    "tipo_id": tipo, "sitio_id": sitio, "nombre": "SW-CORE-01",
    "hostname": "192.168.10.1", "intervalo_segundos": 60, "activo": True,
    "parametros": {
        "snmp_version": "2c", "port": 161,
        "oids": {"cpu": "1.3.6.1.4.1.6027.3.26.1.4.4.1.5.2.1.1"},
    },
    "secretos": {"snmp_community": comm},
}))
PY
)
RID=$(curl -sk -X POST "$API/api/recursos" -H "$H" -H 'Content-Type: application/json' -d "$BODY" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "SW-CORE-01 creado id=$RID"

echo "esperando 95s a que el worker lo chequee…"
sleep 95
echo "== Estado y último chequeo =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -x -c "SELECT estado_actual, ultimo_chequeo_at FROM recursos WHERE id=$RID"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -x -c "SELECT ts, estado, detalle FROM chequeos WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 1"
echo "== Métricas =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT metrica, valor, unidad FROM metricas WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 6"
