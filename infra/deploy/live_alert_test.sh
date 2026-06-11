#!/usr/bin/env bash
# Prueba end-to-end: crea un recurso caído -> incidencia -> correo, y lo elimina.
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

TIPO=$(curl -sk "$API/api/tipos-recurso?per_page=100" -H "$H" \
  | python3 -c "import sys,json;print(next(x['id'] for x in json.load(sys.stdin)['data'] if x['codigo']=='fibra_wan'))")

BODY=$(python3 - "$TIPO" <<'PY'
import json, sys
print(json.dumps({
    "tipo_id": int(sys.argv[1]), "nombre": "TEST-ALERTA (temporal)",
    "hostname": "192.0.2.1", "intervalo_segundos": 30, "activo": True,
    "parametros": {"metodo": "icmp", "timeout_ms": 1000, "reintentos": 1},
}))
PY
)
RID=$(curl -sk -X POST "$API/api/recursos" -H "$H" -H 'Content-Type: application/json' -d "$BODY" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "recurso de prueba creado id=$RID (192.0.2.1, no responde)"

echo "esperando 95s (resync + chequeo + incidencia + correo)…"
sleep 95

echo "== Incidencia generada =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT id, estado, severidad, titulo FROM incidencias WHERE recurso_id=$RID"
echo "== Notificaciones registradas =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT n.id, n.estado, n.destino, n.intentos FROM notificaciones n JOIN incidencias i ON i.id=n.incidencia_id WHERE i.recurso_id=$RID"
echo "== Log del worker (notif) =="
journalctl -u monitoreo-worker --no-pager -n 400 | grep -Ei "Notif|TEST-ALERTA|incidencia .*$RID|Correo NOC" | tail -8 || echo "(sin líneas)"

echo "== Limpieza: eliminar recurso de prueba =="
curl -sk -o /dev/null -w "DELETE recurso $RID -> HTTP %{http_code}\n" -X DELETE "$API/api/recursos/$RID" -H "$H"
