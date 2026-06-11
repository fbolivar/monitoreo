#!/usr/bin/env bash
# Crea los dos switches Dell de PISO1 vía la API. Env: U/PASS (admin), COMM (community SNMP).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
A="https://127.0.0.1/api"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc"

T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "${U:-}" "${PASS:-}")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
TIPO=$($PSQL "SELECT id FROM tipos_recurso WHERE codigo='switch_lan' LIMIT 1")
SITIO=$($PSQL "SELECT sitio_id FROM recursos WHERE nombre='SW-CORE-01' LIMIT 1")
[ -z "$SITIO" ] && SITIO=null
echo "tipo switch_lan=$TIPO  sitio=$SITIO"

crear() {
  local nombre="$1" ip="$2"
  if [ -n "$($PSQL "SELECT 1 FROM recursos WHERE nombre='$nombre' LIMIT 1")" ]; then
    echo "  $nombre ya existe; se omite."; return
  fi
  local body
  body=$(printf '{"tipo_id":%s,"sitio_id":%s,"nombre":"%s","hostname":"%s","intervalo_segundos":60,"activo":true,"parametros":{"snmp_version":"2c","port":161,"interfaces":true,"oids":{"cpu":"1.3.6.1.4.1.6027.3.26.1.4.4.1.5.2.1.1"}},"secretos":{"snmp_community":"%s"}}' \
    "$TIPO" "$SITIO" "$nombre" "$ip" "$COMM")
  printf "  crear %s (%s) -> " "$nombre" "$ip"
  curl -sk -o /dev/null -w '%{http_code}\n' -X POST "$A/recursos" \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "$body"
}

crear "SW-PISO1-NC-41" "192.168.10.41"
crear "SW-PISO1-NC-46" "192.168.10.46"

echo "esperando un ciclo de chequeo (75s)…"; sleep 75
echo "== estado =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT nombre, hostname, estado_actual, ultimo_chequeo_at FROM recursos WHERE hostname IN ('192.168.10.41','192.168.10.46') ORDER BY nombre"
echo "== interfaces detectadas =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT r.nombre, count(i.*) AS interfaces FROM recursos r LEFT JOIN interfaces i ON i.recurso_id=r.id WHERE r.hostname IN ('192.168.10.41','192.168.10.46') GROUP BY r.nombre ORDER BY r.nombre"
