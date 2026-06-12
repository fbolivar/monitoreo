#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

echo "== Errores recientes del worker (ultimo minuto) =="
journalctl -u monitoreo-worker --since '90 seconds ago' --no-pager | grep -iE 'ERROR|latido|Fallo' | tail -20 || echo '(sin errores recientes)'

echo
echo "== Detalle de un fallo: recheck manual de SW-CORE-01 (23) con traza =="
journalctl -u monitoreo-worker --since '3 minutes ago' --no-pager | grep -iE 'Traceback|Exception|recurso 23' | tail -15 || true

echo
echo "== Estado actual de switches + servidores SNMP =="
$P -c "SELECT t.codigo, r.estado_actual, count(*)
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id
       WHERE r.activo AND t.codigo IN ('switch_lan','servidor')
       GROUP BY 1,2 ORDER BY 1,2"

echo
echo "== Edad del ultimo chequeo por recurso SNMP (segundos) =="
$P -c "SELECT r.nombre, r.estado_actual,
          round(EXTRACT(EPOCH FROM (now() - (SELECT max(ts) FROM chequeos WHERE recurso_id=r.id)))) AS hace_seg
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id
       WHERE r.activo AND t.codigo IN ('switch_lan','servidor')
       ORDER BY hace_seg DESC NULLS FIRST LIMIT 8"
