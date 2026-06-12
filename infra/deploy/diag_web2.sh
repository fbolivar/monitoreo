#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

echo "== Último chequeo (estado/latencia/detalle) de los degradados + api =="
$P -c "SELECT r.nombre, c.estado, c.latencia_ms,
              c.detalle->>'http_status' AS http, c.detalle->>'motivo' AS motivo, c.detalle->>'error' AS error
       FROM recursos r JOIN LATERAL (SELECT * FROM chequeos WHERE recurso_id=r.id ORDER BY ts DESC LIMIT 1) c ON true
       WHERE r.hostname IN ('https://visor.parquesnacionales.gov.co',
                            'https://uparques.parquesnacionales.gov.co',
                            'https://api.parquesnacionales.gov.co')
          OR r.nombre IN ('UParques','Sitio Web')
       ORDER BY r.nombre"

echo "== Umbrales activos que aplican a sitio_web =="
$P -c "SELECT u.id, u.metrica, u.operador, u.valor_warning, u.valor_critical, u.duracion_segundos, u.recurso_id, u.tipo_id
       FROM umbrales u
       WHERE u.activo AND (u.tipo_id=(SELECT id FROM tipos_recurso WHERE codigo='sitio_web')
             OR u.metrica IN ('http_status','latency','ssl_dias_restantes'))"

echo "== Incidencias abiertas de sitios web =="
$P -c "SELECT i.recurso_id, r.nombre, i.severidad, i.titulo, i.estado
       FROM incidencias i JOIN recursos r ON r.id=i.recurso_id
       JOIN tipos_recurso t ON t.id=r.tipo_id
       WHERE t.codigo='sitio_web' AND i.estado!='resuelta' ORDER BY r.nombre"

echo "== Prueba directa a api (curl, ver qué responde de verdad) =="
curl -skI --max-time 10 https://api.parquesnacionales.gov.co | head -5 || echo "curl fallo"
echo "---raiz GET código---"
curl -sk -o /dev/null -w 'http=%{http_code} tiempo=%{time_total}s\n' --max-time 10 https://api.parquesnacionales.gov.co || true
