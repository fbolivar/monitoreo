#!/usr/bin/env bash
# =====================================================================
# 36_sintetico.sh — Chequeos sintéticos multipaso (sin migración).
# Probe nuevo que ejecuta una transacción HTTP de varios pasos (login->consulta,
# content/JSON-path, fases DNS/TCP/TLS). Solo worker + frontend; reusa el pipeline
# de estado/incidencias/metricas existente. Opt-in via parametros.pasos.
# =====================================================================
set -uo pipefail

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Rebuild frontend =="
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Reiniciar worker (carga el probe sintético) =="
systemctl restart monitoreo-worker
sleep 4
systemctl is-active monitoreo-worker

echo "== LISTO: chequeos sintéticos multipaso desplegados =="
echo "   Activar en un sitio_web: parametros.pasos = [{nombre,metodo,path,esperar_status,contiene,json_path,extraer,max_ms}, ...]"
