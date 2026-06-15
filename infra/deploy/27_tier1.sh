#!/usr/bin/env bash
# =====================================================================
# 27_tier1.sh — MEJORAS 5ª OLA (Tier 1: profundidad técnica del monitoreo)
#   · Estados SOFT/HARD (migr 0013)  · Triggers compuestos (migr 0014)
#   · Freshness / stale-data (sin migración, solo worker)
# Despliega desde GitHub, aplica migraciones, reconstruye API/frontend,
# reinicia el worker y verifica. Idempotente (migraciones con IF NOT EXISTS).
# Requiere /root/monitoreo-secrets.env. Opcional: U/PASS (admin) para probar /api/reglas.
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

echo "== Migraciones 0013 (SOFT/HARD) + 0014 (reglas) =="
"${PSQL[@]}" -f db/migrations/0013_soft_hard.up.sql && echo "  0013 OK"
"${PSQL[@]}" -f db/migrations/0014_reglas.up.sql && echo "  0014 OK"

echo "== Verificación de esquema =="
"${PSQL[@]}" -c "SELECT column_name FROM information_schema.columns
  WHERE table_name='recursos' AND column_name IN
  ('estado_hard','estado_candidato','intentos_estado','max_check_attempts') ORDER BY 1;"
"${PSQL[@]}" -c "SELECT to_regclass('public.reglas') AS tabla_reglas;"

echo "== API Laravel (rutas/controladores nuevos) =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reinicio del worker (nuevo motor) =="
systemctl restart monitoreo-worker
sleep 3
systemctl is-active monitoreo-worker && echo "  worker activo"

echo "== Verificación funcional =="
curl -sk -o /dev/null -w '  GET /api/reglas (sin token) -> %{http_code} (esperado 401)\n' "$A/reglas"

# Si se pasan credenciales admin (U/PASS), prueba el CRUD de reglas de punta a punta.
if [ -n "${U:-}" ] && [ -n "${PASS:-}" ]; then
  T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
    -d "$(printf '{"email":"%s","password":"%s"}' "$U" "$PASS")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
  echo "== Prueba CRUD de reglas (token admin) =="
  TIPO=$("${PSQL[@]}" -tAc "SELECT id FROM tipos_recurso ORDER BY id LIMIT 1")
  RID=$(curl -sk -X POST "$A/reglas" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
    -d "$(printf '{"tipo_id":%s,"nombre":"smoke tier1","severidad":"warning","expresion":{"and":[{"metrica":"cpu","op":">","valor":90},{"metrica":"mem","op":">","valor":85}]}}' "$TIPO")" \
    | sed -E 's/.*"id":([0-9]+).*/\1/')
  echo "  regla creada id=$RID"
  curl -sk -o /dev/null -w '  expresion inválida -> %{http_code} (esperado 422)\n' -X POST "$A/reglas" \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
    -d "$(printf '{"tipo_id":%s,"nombre":"mala","expresion":{"metrica":"cpu","op":"=>","valor":1}}' "$TIPO")"
  [ -n "${RID:-}" ] && curl -sk -o /dev/null -w '  DELETE regla smoke -> %{http_code} (esperado 204)\n' \
    -X DELETE "$A/reglas/$RID" -H "Authorization: Bearer $T"
fi

echo "== Estado SOFT/HARD de una muestra de recursos =="
"${PSQL[@]}" -c "SELECT id, nombre, estado_actual, estado_hard, estado_candidato, intentos_estado, max_check_attempts
  FROM recursos WHERE activo ORDER BY id LIMIT 8;"

echo "== LISTO: Tier 1 desplegado =="
