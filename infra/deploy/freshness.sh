#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "
SELECT t.codigo,
       count(*) AS total,
       round(avg(EXTRACT(EPOCH FROM (now()-x.ult)))) AS edad_prom_seg,
       round(max(EXTRACT(EPOCH FROM (now()-x.ult)))) AS edad_max_seg
FROM (
  SELECT r.id, tt.codigo, (SELECT max(ts) FROM chequeos WHERE recurso_id=r.id) AS ult
  FROM recursos r JOIN tipos_recurso tt ON tt.id=r.tipo_id
  WHERE r.activo AND tt.codigo IN ('switch_lan','servidor','sitio_web')
) x JOIN tipos_recurso t ON t.codigo=x.codigo
GROUP BY 1 ORDER BY 1;"
