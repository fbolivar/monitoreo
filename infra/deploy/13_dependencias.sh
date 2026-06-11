#!/usr/bin/env bash
# Despliega dependencias padre→hijo: migración 0005, worker, API, frontend.
# Verifica: columna, relación en API, guardia anti-ciclo y supresión (CTE) con ROLLBACK.
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0005: depende_de_id =="
$PSQL -f db/migrations/0005_dependencias.up.sql
$PSQL -c "\d recursos" | grep -i depende_de || true

echo "== API: limpiar caché =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -4 )
systemctl reload nginx

echo "== Reiniciar worker =="
systemctl restart monitoreo-worker

# IDs de los equipos reales
SRV=$($PSQL -tAc "SELECT id FROM recursos WHERE nombre='PNNCSRVNCFHV2'")
SW=$($PSQL -tAc "SELECT id FROM recursos WHERE nombre='SW-CORE-01'")
echo "PNNCSRVNCFHV2=$SRV  SW-CORE-01=$SW"

TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

echo "== API: el servidor depende del switch (PUT) =="
curl -sk -X PUT "https://127.0.0.1/api/recursos/$SRV" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"depende_de_id\": $SW}" \
  | sed -E 's/.*("depende_de"[^}]*\}).*/\1/' ; echo

echo "== API: intento de ciclo (switch -> servidor) debe dar 422 =="
curl -sk -o /dev/null -w 'HTTP %{http_code} (esperado 422)\n' -X PUT "https://127.0.0.1/api/recursos/$SW" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"depende_de_id\": $SRV}"

echo "== API: autodependencia debe dar 422 =="
curl -sk -o /dev/null -w 'HTTP %{http_code} (esperado 422)\n' -X PUT "https://127.0.0.1/api/recursos/$SRV" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"depende_de_id\": $SRV}"

echo "== Supresión (prueba transaccional, sin persistir): si el switch estuviera 'down' =="
$PSQL <<SQL
BEGIN;
UPDATE recursos SET estado_actual='down' WHERE id=$SW;
SELECT 'ancestro_caido del servidor => ' || coalesce((
  WITH RECURSIVE cadena AS (
    SELECT id, depende_de_id, estado_actual, nombre, 1 AS nivel
    FROM recursos WHERE id = (SELECT depende_de_id FROM recursos WHERE id=$SRV)
    UNION ALL
    SELECT r.id, r.depende_de_id, r.estado_actual, r.nombre, c.nivel+1
    FROM recursos r JOIN cadena c ON r.id=c.depende_de_id WHERE c.nivel < 20
  )
  SELECT nombre FROM cadena WHERE estado_actual='down' ORDER BY nivel LIMIT 1
), '(ninguno)') AS resultado;
ROLLBACK;
SQL

echo "== Estado actual (sin cambios tras ROLLBACK) =="
$PSQL -c "SELECT nombre, estado_actual, depende_de_id FROM recursos WHERE id IN ($SRV,$SW) ORDER BY nombre"
