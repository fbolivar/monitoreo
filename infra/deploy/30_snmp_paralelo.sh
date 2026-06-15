#!/usr/bin/env bash
# =====================================================================
# 30_snmp_paralelo.sh — Polling SNMP paralelo (SnmpEngine+loop thread-local).
# Solo worker: git pull + reinicio + benchmark de paralelismo. Sin migración.
# =====================================================================
set -uo pipefail

cd /opt/monitoreo
echo "== Sync con GitHub =="
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

echo "== Reinicio del worker (cliente SNMP nuevo) =="
systemctl restart monitoreo-worker
sleep 3
systemctl is-active monitoreo-worker && echo "  worker activo"

echo "== Benchmark de paralelismo SNMP =="
PY=$(ls /opt/monitoreo/monitor/.venv/bin/python 2>/dev/null || ls /opt/monitoreo/monitor/venv/bin/python 2>/dev/null || echo python3)
( cd /opt/monitoreo/monitor && "$PY" ../infra/deploy/bench_snmp.py ) || echo "  (benchmark falló; revisar)"

echo "== LISTO =="
