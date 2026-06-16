#!/usr/bin/env bash
# =====================================================================
# 32_servicios.sh — Observabilidad de servicios (Camino A) [migr. 0018].
# Aplica migración, reconstruye API/frontend y siembra UNA transacción de
# ejemplo (si no hay ninguna) encadenando recursos reales, para que la
# pantalla "Servicios" muestre el análisis de correlación de inmediato.
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

echo "== Migración 0018 (servicios) =="
"${PSQL[@]}" -f db/migrations/0018_servicios.up.sql && echo "  0018 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.servicios') AS servicios, to_regclass('public.servicio_componentes') AS componentes;"

echo "== API Laravel (CRUD servicios + /analisis) =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Seed: transacción de ejemplo (solo si no hay ninguna) =="
"${PSQL[@]}" <<'SQL'
DO $$
DECLARE sid bigint;
BEGIN
  IF (SELECT count(*) FROM servicios) = 0 THEN
    INSERT INTO servicios (nombre, descripcion, objetivo_ms, impacto_negocio)
    VALUES ('Portal de servicios (demo)',
            'Ejemplo: encadena recursos reales para correlacionar latencias y ubicar el cuello de botella.',
            2000,
            'Lentitud en la página -> mayor abandono y afectación directa en conversión y ventas.')
    RETURNING id INTO sid;
    INSERT INTO servicio_componentes (servicio_id, orden, nombre, tipo, recurso_id)
    SELECT sid, v.orden, v.nombre, v.tipo, v.recurso_id
    FROM (VALUES
      (0, 'Web',           'web',     (SELECT id FROM recursos WHERE nombre ILIKE 'Sitio Web%' LIMIT 1)),
      (1, 'API Gateway',   'gateway', (SELECT id FROM recursos WHERE nombre ILIKE 'FortiGate%' LIMIT 1)),
      (2, 'Catálogo',      'api',     (SELECT id FROM recursos WHERE nombre ILIKE 'PNNCSRVNCFDC01%' LIMIT 1)),
      (3, 'Base de Datos', 'db',      (SELECT id FROM recursos WHERE nombre ILIKE 'PNNCSRVNCFFS02%' LIMIT 1))
    ) AS v(orden, nombre, tipo, recurso_id);
    RAISE NOTICE 'Servicio demo creado (id %).', sid;
  ELSE
    RAISE NOTICE 'Ya existen servicios; no se siembra el demo.';
  END IF;
END $$;
SQL

echo "== Verificación =="
curl -sk -o /dev/null -w '  GET /api/servicios (sin token) -> %{http_code} (esperado 401)\n' "$A/servicios"
echo "  servicios y componentes:"
"${PSQL[@]}" -c "SELECT s.id, s.nombre, s.objetivo_ms, count(c.id) AS componentes
  FROM servicios s LEFT JOIN servicio_componentes c ON c.servicio_id=s.id GROUP BY s.id ORDER BY s.id;"
"${PSQL[@]}" -c "SELECT c.orden, c.nombre, c.tipo, r.nombre AS recurso, r.estado_actual
  FROM servicio_componentes c LEFT JOIN recursos r ON r.id=c.recurso_id ORDER BY c.servicio_id, c.orden;"

echo "== LISTO: observabilidad de servicios desplegada =="
