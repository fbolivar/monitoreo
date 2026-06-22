#!/usr/bin/env bash
# FASE 6 · Paso Worker: venv + deps + .env + tests + servicio systemd.
set -euo pipefail

REPO=/opt/monitoreo
MON="$REPO/monitor"
source /root/monitoreo-secrets.env

echo "== venv + dependencias =="
cd "$MON"
python3 -m venv .venv
. .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "deps OK"

echo "== .env del worker =="
umask 077
cat > "$MON/.env" <<EOF
DB_HOST=127.0.0.1
DB_PORT=5432
DB_DATABASE=monitoreo
DB_USERNAME=monitoreo
DB_PASSWORD=${DB_PASSWORD}
DB_SSLMODE=prefer
DB_POOL_MAX=8
APP_CRYPTO_KEY=${APP_CRYPTO_KEY}
PROBE_TIMEOUT_MS=3000
ICMP_PRIVILEGED=true
ICMP_COUNT=4
SCHEDULER_MAX_WORKERS=20
TAREAS_MANTENIMIENTO=true
HEALTH_ENABLED=true
HEALTH_PORT=8090
NOTIF_ENABLED=false
LOG_LEVEL=INFO
EOF

echo "== Tests (lógica pura) =="
pytest -q 2>&1 | tail -6 || echo "(pytest con fallos: ver arriba)"

echo "== Servicio systemd =="
cat > /etc/systemd/system/monitoreo-worker.service <<EOF
[Unit]
Description=Monitoreo TI - Worker
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory=${MON}
ExecStart=${MON}/.venv/bin/python ${MON}/main.py
Restart=on-failure
RestartSec=5
# Apagado limpio: main.py espera a los chequeos en vuelo (scheduler wait=True) antes
# de cerrar el pool. 60s acota la espera si un job se cuelga (los walks SNMP terminan
# mucho antes; solo el backup SSH de las 02:00 podría excederlo -> SIGKILL silencioso).
TimeoutStopSec=60
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now monitoreo-worker >/dev/null 2>&1
echo "servicio habilitado e iniciado; esperando un ciclo de chequeos…"
sleep 45

echo "== Estado del servicio =="
systemctl is-active monitoreo-worker
journalctl -u monitoreo-worker --no-pager -n 12 | tail -12

echo "== Health =="
curl -s http://127.0.0.1:8090/health || echo "(health no respondió)"; echo

echo "== Datos escritos por el worker =="
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc"
echo -n "chequeos: "; $PSQL "SELECT count(*) FROM chequeos"
echo -n "metricas: "; $PSQL "SELECT count(*) FROM metricas"
echo "estado_actual de recursos:"
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c "SELECT estado_actual, count(*) FROM recursos GROUP BY estado_actual ORDER BY estado_actual"
