#!/usr/bin/env bash
# Portal público www.parquesnacionales.gov.co (recurso 25): es un CMS pesado cuya
# latencia oscila 2.1-3.8s y cruzaba el umbral global (3000ms) → flapping up/degraded.
# Se le da un umbral de latencia PROPIO (más alto + anti-flapping) que prevalece sobre
# el de tipo, y se corrige parametros [] -> {}.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
$P -c "UPDATE recursos SET parametros='{}'::jsonb WHERE id=25 AND jsonb_typeof(parametros)<>'object'"
$P -c "DELETE FROM umbrales WHERE recurso_id=25 AND metrica='latency'"
$P -c "INSERT INTO umbrales (recurso_id, metrica, operador, valor_warning, valor_critical, duracion_segundos, activo)
       VALUES (25,'latency','>',6000,12000,120,true)"
$P -c "UPDATE incidencias SET estado='resuelta', resuelta_at=now() WHERE recurso_id=25 AND estado<>'resuelta'"
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py 25 >/dev/null 2>&1 )
$P -c "SELECT id, nombre, hostname, estado_actual FROM recursos WHERE id=25"
