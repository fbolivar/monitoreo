#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
echo "== Último chequeo de visor / uparques / api =="
$P -c "SELECT r.nombre, c.estado, c.detalle->>'http_status' AS http, c.detalle->>'motivo' AS motivo,
              c.detalle->'evaluacion'->>'estado' AS eval, c.detalle->'evaluacion'->>'motivos' AS eval_motivos, c.latencia_ms
       FROM recursos r JOIN LATERAL (SELECT * FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) c ON true
       WHERE r.hostname IN ('https://visor.parquesnacionales.gov.co','https://uparques.parquesnacionales.gov.co','https://api.parquesnacionales.gov.co')"
echo "== Umbrales que aplican a sitio_web =="
$P -c "SELECT u.metrica, u.operador, u.valor_warning, u.valor_critical, u.duracion_segundos, u.recurso_id, u.tipo_id
       FROM umbrales u WHERE u.activo AND (u.tipo_id=(SELECT id FROM tipos_recurso WHERE codigo='sitio_web')
             OR u.metrica IN ('http_status','latency'))"
