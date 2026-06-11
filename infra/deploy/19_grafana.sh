#!/usr/bin/env bash
# Instala Grafana y lo provisiona contra el Postgres de SIMON (solo lectura).
# Acceso: http://<servidor>:3000  (admin/admin al primer ingreso → cambiar).
set -euo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git pull --ff-only origin main >/dev/null 2>&1 || true

echo "== 1) Instalar Grafana (repo oficial) =="
if ! command -v grafana-server >/dev/null 2>&1 && ! dpkg -l | grep -q '^ii  grafana'; then
  apt-get install -y apt-transport-https software-properties-common wget >/dev/null
  mkdir -p /etc/apt/keyrings
  wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor > /etc/apt/keyrings/grafana.gpg
  echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
    > /etc/apt/sources.list.d/grafana.list
  apt-get update >/dev/null
  apt-get install -y grafana >/dev/null
else
  echo "  Grafana ya instalado."
fi

echo "== 2) Rol Postgres de solo lectura =="
GPW=$(grep -E '^GRAFANA_RO_PW=' /root/monitoreo-secrets.env | cut -d= -f2-)
if [ -z "${GPW:-}" ]; then
  GPW=$(openssl rand -base64 24 | tr -d '/+=' | head -c 28)
  echo "GRAFANA_RO_PW=$GPW" >> /root/monitoreo-secrets.env
  echo "  generada GRAFANA_RO_PW (guardada en monitoreo-secrets.env)"
fi
$PSQL -v gpw="$GPW" -f infra/grafana/grafana_ro.sql

echo "== 3) Provisionar datasource + dashboards =="
install -d /etc/grafana/provisioning/datasources /etc/grafana/provisioning/dashboards /var/lib/grafana/dashboards
sed "s|__GRAFANA_RO_PW__|$GPW|" infra/grafana/provisioning/datasources/simon.yaml.tmpl \
  > /etc/grafana/provisioning/datasources/simon.yaml
cp infra/grafana/provisioning/dashboards/simon.yaml /etc/grafana/provisioning/dashboards/simon.yaml
cp infra/grafana/dashboards/simon.json /var/lib/grafana/dashboards/simon.json
chown -R grafana:grafana /var/lib/grafana/dashboards 2>/dev/null || true

echo "== 4) Firewall + arranque =="
ufw allow 3000/tcp >/dev/null 2>&1 || true
systemctl enable --now grafana-server >/dev/null 2>&1 || systemctl restart grafana-server
sleep 5
systemctl is-active grafana-server
echo "  Datasource RO:"; $PSQL -tAc "SELECT rolname FROM pg_roles WHERE rolname='grafana_ro'"
curl -s -o /dev/null -w '  GET :3000 -> %{http_code}\n' http://127.0.0.1:3000/login || true
echo "Listo. Abre http://192.168.50.54:3000 (admin/admin la 1ª vez; cámbiala)."
