#!/usr/bin/env bash
# Verificación integral (solo lectura) tras consolidar las mejoras del roadmap.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
echo "== Commit desplegado =="; git log --oneline -1

echo "== Servicios =="
for s in monitoreo-worker simon-traps grafana-server nginx php8.2-fpm postgresql; do
  printf "  %-18s " "$s"; systemctl is-active "$s" 2>/dev/null || true
done
printf "  %-18s " ufw; ufw status 2>/dev/null | head -1

echo "== Esquema de features (tablas) =="
$PSQL -c "SELECT table_name FROM information_schema.tables
          WHERE table_schema='public'
            AND table_name IN ('interfaces','interfaces_historico','auditoria')
          ORDER BY 1"
echo "  columnas clave:"
$PSQL -tAc "SELECT '   recursos.depende_de_id  -> ' || count(*) FROM information_schema.columns WHERE table_name='recursos' AND column_name='depende_de_id'"
$PSQL -tAc "SELECT '   interfaces.monitorear   -> ' || count(*) FROM information_schema.columns WHERE table_name='interfaces' AND column_name='monitorear'"
$PSQL -tAc "SELECT '   incidencias.if_index    -> ' || count(*) FROM information_schema.columns WHERE table_name='incidencias' AND column_name='if_index'"

echo "== Conteos =="
$PSQL -c "SELECT estado_actual, count(*) FROM recursos GROUP BY 1 ORDER BY 2 DESC"
for t in chequeos metricas interfaces interfaces_historico auditoria traps; do
  printf "  %-22s " "$t"; $PSQL -tAc "SELECT count(*) FROM $t"
done
printf "  %-22s " "incidencias_abiertas"; $PSQL -tAc "SELECT count(*) FROM incidencias WHERE estado<>'resuelta'"

echo "== Endpoints HTTPS (con token admin) =="
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')
for ep in "recursos" "reportes/disponibilidad?rango=24h" "auditoria?per_page=1"; do
  code=$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1/api/$ep" -H "Authorization: Bearer $TOKEN")
  printf "  /api/%-35s -> %s\n" "$ep" "$code"
done
printf "  %-41s -> %s\n" "/ (SPA)" "$(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/)"

echo "== Worker: errores recientes =="
journalctl -u monitoreo-worker --no-pager -n 300 2>/dev/null \
  | grep -iE "error|exception|traceback" | tail -8 || echo "  (sin errores)"

echo "== Backups y cron =="
crontab -l 2>/dev/null | grep -iE "dump|backup|monitoreo" || echo "  (sin cron de root)"
ls -lh /var/backups/monitoreo/ 2>/dev/null | tail -4 || echo "  (ruta /var/backups/monitoreo no existe)"
