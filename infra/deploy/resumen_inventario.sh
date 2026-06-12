#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
echo "== Recursos ACTIVOS por estado =="
$P -c "SELECT estado_actual, count(*) FROM recursos WHERE activo GROUP BY 1 ORDER BY 2 DESC"
echo "== Por tipo (activos) =="
$P -c "SELECT t.nombre AS tipo, count(*) FILTER (WHERE r.activo) AS activos, count(*) FILTER (WHERE NOT r.activo) AS en_pausa
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id GROUP BY t.nombre ORDER BY 2 DESC"
echo "== Servidores Windows (estado + CPU/mem último) =="
$P -c "SELECT r.nombre, r.estado_actual,
              (SELECT round(valor) FROM metricas WHERE recurso_id=r.id AND metrica='cpu' ORDER BY ts DESC LIMIT 1) AS cpu,
              (SELECT round(valor) FROM metricas WHERE recurso_id=r.id AND metrica='mem' ORDER BY ts DESC LIMIT 1) AS mem
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id
       WHERE t.codigo='servidor' AND r.activo ORDER BY r.nombre"
