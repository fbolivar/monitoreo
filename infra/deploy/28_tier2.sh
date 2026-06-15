#!/usr/bin/env bash
# =====================================================================
# 28_tier2.sh — MEJORAS 6ª OLA (Tier 2: profundidad de métricas)
#   · ICMP enriquecido (jitter/rtt_min/rtt_max)  · Forecasting de capacidad (migr 0015)
# Despliega desde GitHub, aplica la migración, reconstruye API/frontend, reinicia
# el worker, DISPARA el forecast una vez y verifica. Idempotente.
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

echo "== Migración 0015 (pronosticos) =="
"${PSQL[@]}" -f db/migrations/0015_pronosticos.up.sql && echo "  0015 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.pronosticos') AS tabla_pronosticos;"

echo "== API Laravel (ruta /pronosticos) =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reinicio del worker (ICMP enriquecido + job forecast) =="
systemctl restart monitoreo-worker
sleep 3
systemctl is-active monitoreo-worker && echo "  worker activo"

echo "== Disparar forecast una vez (normalmente corre 00:30) =="
PY=$(ls /opt/monitoreo/monitor/.venv/bin/python 2>/dev/null || ls /opt/monitoreo/monitor/venv/bin/python 2>/dev/null || echo python3)
( cd /opt/monitoreo/monitor && "$PY" -c "from monitor.config import cargar_settings; from monitor.db import Database; from monitor.runner import pronosticar_capacidad; s=cargar_settings(); db=Database(s); pronosticar_capacidad(db,s); print('  forecast ejecutado')" ) || echo "  (forecast: revisar; quizá poca historia aún)"

echo "== Verificación funcional =="
curl -sk -o /dev/null -w '  GET /api/pronosticos (sin token) -> %{http_code} (esperado 401)\n' "$A/pronosticos"
echo -n "  filas en pronosticos: "; "${PSQL[@]}" -tAc "SELECT count(*) FROM pronosticos"
echo "  top pronósticos (con proyección):"
"${PSQL[@]}" -c "SELECT p.recurso_id, left(r.nombre,26) AS nombre, p.metrica, round(p.valor_actual::numeric,1) AS actual,
  round(p.pendiente_dia::numeric,3) AS pend_dia, round(p.dias_restantes::numeric,0) AS dias, round(p.r2::numeric,2) AS r2, p.muestras
  FROM pronosticos p JOIN recursos r ON r.id=p.recurso_id ORDER BY p.dias_restantes ASC NULLS LAST LIMIT 12;"

echo "== ICMP enriquecido: ¿hay métrica 'jitter' reciente? =="
"${PSQL[@]}" -c "SELECT count(DISTINCT recurso_id) AS recursos_con_jitter
  FROM metricas WHERE metrica='jitter' AND ts > now()-interval '5 min';"

echo "== LISTO: Tier 2 desplegado =="
