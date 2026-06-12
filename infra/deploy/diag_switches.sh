#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "esperando un ciclo más…"; sleep 35
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT id, nombre, hostname, estado_actual, (secretos IS NOT NULL) AS tiene_sec, parametros->>'snmp_version' AS ver
   FROM recursos WHERE hostname IN ('192.168.10.41','192.168.10.46') ORDER BY hostname, nombre"
echo "== último chequeo (motivo del unknown/down) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT r.nombre, c.estado, c.detalle->>'error' AS error, c.detalle->>'motivo' AS motivo, c.detalle->>'oids_sin_respuesta' AS sin_resp
   FROM recursos r JOIN LATERAL (SELECT * FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) c ON true
   WHERE r.hostname IN ('192.168.10.41','192.168.10.46') ORDER BY r.nombre"
