#!/usr/bin/env bash
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "esperando 75s…"; sleep 75
echo "== Estado FortiGate-Principal (id 21) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT estado_actual, ultimo_chequeo_at FROM recursos WHERE id=21"
echo "== Último chequeo (detalle) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -x -c "SELECT ts, estado, latencia_ms, detalle FROM chequeos WHERE recurso_id=21 ORDER BY ts DESC LIMIT 1"
echo "== Métricas =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT metrica, valor, unidad FROM metricas WHERE recurso_id=21 ORDER BY ts DESC LIMIT 8"
echo "== Log worker (FortiGate) =="
journalctl -u monitoreo-worker --no-pager -n 300 | grep -Ei "fortigate|recurso 21|Chequeo 2[0-9] \(FortiGate" | tail -6 || echo "(sin líneas)"
