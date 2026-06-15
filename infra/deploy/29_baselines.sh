#!/usr/bin/env bash
# =====================================================================
# 29_baselines.sh — Baselining estacional / detección de anomalías (Tier 2 #5)
#   migr 0016 (baselines) + job recalcular_baselines + _detectar_anomalias (opt-in).
# Despliega, aplica la migración, reconstruye API/frontend, reinicia el worker,
# DISPARA el recálculo una vez y verifica. Idempotente.
# =====================================================================
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL=(psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1)
A="https://127.0.0.1/api"

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Migración 0016 (baselines) =="
"${PSQL[@]}" -f db/migrations/0016_baselines.up.sql && echo "  0016 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.baselines') AS tabla_baselines;"

echo "== API Laravel (ruta /recursos/{id}/baselines) =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reinicio del worker (_detectar_anomalias + job baselines) =="
systemctl restart monitoreo-worker
sleep 3
systemctl is-active monitoreo-worker && echo "  worker activo"

echo "== Disparar recálculo de líneas base una vez (normalmente 00:45) =="
PY=$(ls /opt/monitoreo/monitor/.venv/bin/python 2>/dev/null || ls /opt/monitoreo/monitor/venv/bin/python 2>/dev/null || echo python3)
( cd /opt/monitoreo/monitor && "$PY" -c "from monitor.config import cargar_settings; from monitor.db import Database; from monitor.runner import recalcular_baselines; s=cargar_settings(); db=Database(s); recalcular_baselines(db,s); print('  baselines recalculadas')" ) || echo "  (revisar: ¿poca historia aún?)"

echo "== Verificación =="
echo -n "  franjas en baselines: "; "${PSQL[@]}" -tAc "SELECT count(*) FROM baselines"
echo -n "  franjas maduras (>=7 dias): "; "${PSQL[@]}" -tAc "SELECT count(*) FROM baselines WHERE muestras >= 7"
echo "  muestra de líneas base (top por nº de muestras):"
"${PSQL[@]}" -c "SELECT b.recurso_id, left(r.nombre,22) AS nombre, b.metrica, b.hora,
  round(b.media::numeric,1) AS media, round(b.desviacion::numeric,2) AS sigma, b.muestras
  FROM baselines b JOIN recursos r ON r.id=b.recurso_id ORDER BY b.muestras DESC, b.recurso_id LIMIT 10;"

# Sugerencia: activar anomalías en los servidores (cpu/mem) si aún no está.
echo "== Recursos con baseline opt-in (parametros.baseline_metricas) =="
"${PSQL[@]}" -c "SELECT id, nombre, parametros->'baseline_metricas' AS metricas
  FROM recursos WHERE parametros ? 'baseline_metricas';"

echo "== LISTO: baselining desplegado =="
