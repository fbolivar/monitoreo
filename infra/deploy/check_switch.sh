#!/usr/bin/env bash
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "esperando 50s…"; sleep 50
echo "== Estado SW-CORE-01 (id 23) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT estado_actual, ultimo_chequeo_at FROM recursos WHERE id=23"
echo "== Último chequeo (detalle) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -x -c "SELECT ts, estado, detalle FROM chequeos WHERE recurso_id=23 ORDER BY ts DESC LIMIT 1"
echo "== Métricas =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT metrica, valor, unidad, ts FROM metricas WHERE recurso_id=23 ORDER BY ts DESC LIMIT 6"
echo "== Log worker (SW-CORE-01 / recurso 23) =="
journalctl -u monitoreo-worker --no-pager -n 400 | grep -Ei "SW-CORE-01|Chequeo 23 |recurso 23" | tail -8 || echo "(sin líneas)"
