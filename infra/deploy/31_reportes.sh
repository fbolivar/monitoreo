#!/usr/bin/env bash
# =====================================================================
# 31_reportes.sh — Reportes programados de SLA por correo (migr 0017).
# Aplica migración, instala fpdf2 en el venv, reconstruye API/frontend, reinicia
# el worker y VERIFICA la generación del PDF con datos reales (sin enviar correo).
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

echo "== Migración 0017 (reportes_programados) =="
"${PSQL[@]}" -f db/migrations/0017_reportes_programados.up.sql && echo "  0017 OK"
"${PSQL[@]}" -c "SELECT to_regclass('public.reportes_programados') AS tabla;"

echo "== Dependencia fpdf2 en el venv del worker =="
PY=$(ls /opt/monitoreo/monitor/.venv/bin/python 2>/dev/null || ls /opt/monitoreo/monitor/venv/bin/python 2>/dev/null || echo python3)
"$PY" -m pip install -q 'fpdf2==2.7.9' && echo "  fpdf2 instalado"

echo "== API Laravel (CRUD reportes-programados) =="
( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reinicio del worker (job reportes-programados) =="
systemctl restart monitoreo-worker
sleep 3
systemctl is-active monitoreo-worker && echo "  worker activo"

echo "== Verificación funcional =="
curl -sk -o /dev/null -w '  GET /api/reportes-programados (sin token) -> %{http_code} (esperado 401)\n' "$A/reportes-programados"
journalctl -u monitoreo-worker --no-pager -n 60 | grep -i 'Reportes programados activos' | tail -1 || echo "  (job no logueado aún)"

echo "== Generación de PDF con datos reales (sin enviar correo) =="
( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor "$PY" -c "
from monitor.config import cargar_settings
from monitor.db import Database
from monitor import repository as repo, reportes as rep
s=cargar_settings(); db=Database(s)
filas=repo.disponibilidad(db, rep.rango_segundos('30d'))
resumen=rep.kpis(filas)
pdf=rep.generar_pdf(filas,'Reporte de disponibilidad — PRUEBA','últimos 30 días','prueba',resumen)
if pdf:
    open('/tmp/reporte_test.pdf','wb').write(pdf)
    print('  PDF generado:', len(pdf), 'bytes | recursos:', len(filas), '| disp.promedio:', resumen['disponibilidad_promedio'])
else:
    print('  fpdf2 no disponible -> el worker usaría CSV. recursos:', len(filas))
" )
[ -f /tmp/reporte_test.pdf ] && { echo -n "  cabecera: "; head -c 5 /tmp/reporte_test.pdf; echo; ls -la /tmp/reporte_test.pdf; }

echo "== LISTO: reportes programados desplegados =="
