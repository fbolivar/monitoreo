#!/usr/bin/env bash
# Corrige: (1) parametros de api roto a lista, (2) umbral de latencia muy estricto
# para sitios web, (3) unifica duplicado UParques (desactiva id 71).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"

echo "== 1. api: reescribir parametros como OBJETO limpio (estaba como lista) =="
$P -c "UPDATE recursos SET parametros='{\"codigos_ok\":[200,301,302,303,404]}'::jsonb
       WHERE hostname='https://api.parquesnacionales.gov.co'"

echo "== 2. Umbral de latencia sitio_web (id 9): 1000/3000 -> 3000/8000 ms =="
echo "   (sitios públicos con redirección tardan 1-2.5s; 1s era demasiado estricto)"
$P -c "UPDATE umbrales SET valor_warning=3000, valor_critical=8000 WHERE id=9"

echo "== 3. Unificar UParques: desactivar el duplicado nuevo (id 71) y resolver su incidencia =="
echo "   Se conserva id 30 'UParques' (224 chequeos + 51 incidencias de historia, URL /login que da 200)"
$P -c "UPDATE recursos SET activo=false WHERE id=71"
$P -c "UPDATE incidencias SET estado='resuelta', resuelta_at=now() WHERE recurso_id=71 AND estado<>'resuelta'"

echo "== 4. Rechequeo inmediato de los sitios web activos =="
IDS=$($Pt "SELECT r.id FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='sitio_web' AND r.activo")
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $IDS >/dev/null 2>&1 )
sleep 1

echo "== 5. Estado final de los sitios web =="
$P -c "SELECT r.id, r.nombre, r.activo, r.estado_actual,
          (SELECT detalle->>'http_status' FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) AS http,
          (SELECT round(latencia_ms) FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) AS lat_ms,
          (SELECT round(valor) FROM metricas WHERE recurso_id=r.id AND metrica='ssl_dias_restantes' ORDER BY ts DESC LIMIT 1) AS ssl
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='sitio_web'
       ORDER BY r.activo DESC, r.estado_actual, r.nombre"

echo "== 6. Incidencias de sitio_web aún abiertas =="
$P -c "SELECT i.recurso_id, r.nombre, i.severidad, i.estado FROM incidencias i
       JOIN recursos r ON r.id=i.recurso_id JOIN tipos_recurso t ON t.id=r.tipo_id
       WHERE t.codigo='sitio_web' AND i.estado<>'resuelta' ORDER BY r.nombre"
