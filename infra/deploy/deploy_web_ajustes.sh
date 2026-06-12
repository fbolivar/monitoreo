#!/usr/bin/env bash
# Despliega la nueva lógica de la sonda HTTP (2xx/3xx=up, 4xx=degraded, 5xx=down)
# y aplica los ajustes a los sitios web (api: aceptar 404; unificar UParques).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"

echo "== 1. Reiniciar worker (ya con http.py nuevo) =="
systemctl restart monitoreo-worker
sleep 2
systemctl is-active monitoreo-worker

echo "== 2. api: aceptar 404 como sano (codigos_ok) =="
$P -c "UPDATE recursos SET parametros = COALESCE(parametros,'{}'::jsonb) || '{\"codigos_ok\":[200,301,302,303,404]}'::jsonb
       WHERE hostname='https://api.parquesnacionales.gov.co'"

echo "== 3. Duplicado UParques: filas candidatas =="
$P -c "SELECT id, nombre, hostname, activo, estado_actual,
              (SELECT count(*) FROM chequeos WHERE recurso_id=r.id) AS chequeos,
              (SELECT count(*) FROM incidencias WHERE recurso_id=r.id) AS incidencias
       FROM recursos r WHERE nombre ILIKE '%uparques%' OR hostname ILIKE '%uparques%' ORDER BY id"

echo "== 4. Rechequeo inmediato de TODOS los sitios web activos =="
IDS=$($Pt "SELECT r.id FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='sitio_web' AND r.activo")
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $IDS >/dev/null 2>&1 )

echo "== 5. Estado final de los sitios web =="
$P -c "SELECT r.nombre, r.activo, r.estado_actual,
          (SELECT detalle->>'http_status' FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) AS http,
          (SELECT round(valor) FROM metricas WHERE recurso_id=r.id AND metrica='ssl_dias_restantes' ORDER BY ts DESC LIMIT 1) AS ssl
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='sitio_web'
       ORDER BY r.activo DESC, r.estado_actual, r.nombre"
