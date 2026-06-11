#!/usr/bin/env bash
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
echo "esperando 90s para que corran más recursos…"; sleep 90
echo "== chequeos / metricas / incidencias =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT 'chequeos='||count(*) FROM chequeos"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT 'metricas='||count(*) FROM metricas"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT 'incidencias='||count(*) FROM incidencias"
echo "== estado_actual de los 20 recursos =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT estado_actual, count(*) FROM recursos GROUP BY estado_actual ORDER BY 2 DESC"
echo "== muestra de incidencias abiertas =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT r.nombre, i.severidad, i.titulo FROM incidencias i JOIN recursos r ON r.id=i.recurso_id WHERE i.estado<>'resuelta' ORDER BY i.id DESC LIMIT 6"
