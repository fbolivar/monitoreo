#!/usr/bin/env bash
# Fase 2 de interfaces: histórico/gráficas + alerta por puerto monitoreado.
# Migración 0007, worker, API, frontend. Verifica histórico, PATCH monitorear,
# endpoint histórico y el índice de incidencias por interfaz (transaccional).
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0007 =="
$PSQL -f db/migrations/0007_interfaces_fase2.up.sql

echo "== API: limpiar caché =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker =="
systemctl restart monitoreo-worker
echo "esperando ~3 ciclos para acumular histórico…"; sleep 155

RID=$($PSQL -tAc "SELECT id FROM recursos WHERE nombre='SW-CORE-01'")
echo "SW-CORE-01 = $RID"
echo -n "filas en interfaces_historico: "; $PSQL -tAc "SELECT count(*) FROM interfaces_historico WHERE recurso_id=$RID"

IDX=$($PSQL -tAc "SELECT if_index FROM interfaces WHERE recurso_id=$RID AND oper_estado='up' AND in_mbps IS NOT NULL ORDER BY out_mbps DESC NULLS LAST LIMIT 1")
echo "puerto oper-up de prueba: if_index=$IDX"

TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

echo "== PATCH monitorear=true =="
curl -sk -X PUT "https://127.0.0.1/api/recursos/$RID/interfaces/$IDX" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"monitorear": true}'; echo
$PSQL -c "SELECT if_index, if_name, monitorear FROM interfaces WHERE recurso_id=$RID AND if_index=$IDX"

echo "== GET histórico del puerto (rango 24h) =="
curl -sk "https://127.0.0.1/api/recursos/$RID/interfaces/$IDX/historico?rango=24h" \
  -H "Authorization: Bearer $TOKEN" | head -c 400; echo

echo "== PATCH monitorear=false (limpieza, era un puerto up) =="
curl -sk -o /dev/null -w '  -> %{http_code}\n' -X PUT "https://127.0.0.1/api/recursos/$RID/interfaces/$IDX" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"monitorear": false}'

echo "== Índice incidencias por interfaz (transaccional, sin persistir) =="
$PSQL <<SQL
BEGIN;
INSERT INTO incidencias (recurso_id, estado, severidad, titulo) VALUES ($RID,'abierta','warning','TEST principal');
INSERT INTO incidencias (recurso_id, if_index, if_nombre, estado, severidad, titulo) VALUES ($RID,999999,'TEST-PORT','abierta','warning','TEST interfaz');
SELECT 'incidencias abiertas para el recurso (principal + interfaz coexisten): ' ||
       count(*) FILTER (WHERE if_index IS NULL) || ' principal + ' ||
       count(*) FILTER (WHERE if_index IS NOT NULL) || ' interfaz'
FROM incidencias WHERE recurso_id=$RID AND estado<>'resuelta';
ROLLBACK;
SQL
