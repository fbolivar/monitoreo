#!/usr/bin/env bash
RID="${1:?Falta id}"; WAIT="${2:-60}"
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "esperando ${WAIT}s…"; sleep "$WAIT"
echo "== Estado (id $RID) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT nombre, estado_actual, ultimo_chequeo_at FROM recursos WHERE id=$RID"
echo "== Último chequeo (detalle) =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -x -c "SELECT ts, estado, latencia_ms, detalle FROM chequeos WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 1"
echo "== Métricas =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT metrica, valor, unidad, ts FROM metricas WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 8"
echo "== Log worker =="
journalctl -u monitoreo-worker --no-pager -n 300 | grep -Ei "Chequeo $RID |recurso $RID|PNNCSRV" | tail -6 || echo "(sin líneas)"
