#!/usr/bin/env bash
# Pone depende_de = SW-CORE-01 a los switches de piso, y verifica. Env: U/PASS (admin).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
A="https://127.0.0.1/api"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
PSQLt="$PSQL -tAc"

T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "${U:-}" "${PASS:-}")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
CORE=$($PSQLt "SELECT id FROM recursos WHERE nombre='SW-CORE-01' LIMIT 1")
echo "SW-CORE-01 id=$CORE"

echo "== Asignando depende_de=$CORE a los switches de piso =="
for id in $($PSQLt "SELECT id FROM recursos WHERE nombre LIKE 'SW-PISO%' ORDER BY id"); do
  code=$(curl -sk -o /dev/null -w '%{http_code}' -X PUT "$A/recursos/$id" \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "{\"depende_de_id\":$CORE}")
  echo "  recurso $id -> $code"
done

echo "== Verificación (estado + dependencia) =="
$PSQL -c "SELECT nombre, estado_actual, depende_de_id FROM recursos WHERE nombre LIKE 'SW-PISO%' ORDER BY nombre"

echo "== Incidencias abiertas de estos switches =="
$PSQLt "SELECT count(*) FROM incidencias i JOIN recursos r ON r.id=i.recurso_id WHERE r.nombre LIKE 'SW-PISO%' AND i.estado<>'resuelta'"
echo "  (open incidents arriba)"
echo "== Notificaciones recientes (último 30 min) de estos switches =="
$PSQLt "SELECT count(*) FROM notificaciones n JOIN incidencias i ON i.id=n.incidencia_id JOIN recursos r ON r.id=i.recurso_id WHERE r.nombre LIKE 'SW-PISO%' AND n.created_at > now() - interval '30 min'"
