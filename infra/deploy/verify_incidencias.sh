#!/usr/bin/env bash
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc"
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"

# recurso existente cualquiera
RID=$($PSQL "SELECT id FROM recursos ORDER BY id LIMIT 1" | head -1)
IID=$($PSQL "INSERT INTO incidencias (recurso_id, estado, severidad, titulo, abierta_at) VALUES ($RID,'abierta','warning','PRUEBA reconocer/resolver', now()) RETURNING id" | head -1)
echo "incidencia de prueba creada id=$IID (recurso $RID)"

echo "== Reconocer =="
curl -sk -X POST "$API/api/incidencias/$IID/reconocer" -H "$H" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('  estado=',d.get('estado'),' reconocida_por=',d.get('reconocida_por'),' reconocida_at=',d.get('reconocida_at'))"

echo "== Resolver =="
curl -sk -X POST "$API/api/incidencias/$IID/resolver" -H "$H" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('  estado=',d.get('estado'),' resuelta_at=',d.get('resuelta_at'))"

echo "== Resolver de nuevo (debe dar 422) =="
curl -sk -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$API/api/incidencias/$IID/resolver" -H "$H"

echo "== Limpieza (todas las de prueba) =="
$PSQL "DELETE FROM incidencias WHERE titulo='PRUEBA reconocer/resolver'" >/dev/null && echo "  incidencias de prueba eliminadas"
