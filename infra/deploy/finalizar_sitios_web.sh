#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"

echo "== Pausando los que no respondieron =="
$P -c "UPDATE recursos SET activo=false WHERE hostname IN
  ('https://aulaviva.parquesnacionales.gov.co','https://gitea.parquesnacionales.gov.co')"

echo "== Chequeo inmediato de los sitios web activos =="
IDS=$($Pt "SELECT r.id FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='sitio_web' AND r.activo")
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $IDS >/dev/null 2>&1 )

echo "== Estado de los sitios web =="
$P -c "SELECT r.nombre, r.activo, r.estado_actual,
   (SELECT round(valor) FROM metricas WHERE recurso_id=r.id AND metrica='ssl_dias_restantes' ORDER BY ts DESC LIMIT 1) AS ssl_dias
   FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='sitio_web' ORDER BY r.activo DESC, r.estado_actual, r.nombre"
