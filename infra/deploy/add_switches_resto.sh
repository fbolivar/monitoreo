#!/usr/bin/env bash
# Crea el resto de switches Dell (pisos 8, 3, 2) vía la API. Env: U/PASS (admin), COMM (community).
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
  printf "  %s (%s) -> " "$nombre" "$ip"
  curl -sk -o /dev/null -w '%{http_code}\n' -X POST "$A/recursos" \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "$body"
}

LISTA="
SW-PISO8-NC-42 192.168.10.42
SW-PISO8-NC-43 192.168.10.43
SW-PISO8-NC-44 192.168.10.44
SW-PISO8-NC-45 192.168.10.45
SW-PISO3-NC-47 192.168.10.47
SW-PISO3-NC-48 192.168.10.48
SW-PISO3-NC-49 192.168.10.49
SW-PISO3-NC-50 192.168.10.50
SW-PISO2-NC-51 192.168.10.51
SW-PISO2-NC-52 192.168.10.52
SW-PISO2-NC-53 192.168.10.53
SW-PISO2-NC-54 192.168.10.54
"
while read -r nombre ip; do
  [ -z "$nombre" ] && continue
  crear "$nombre" "$ip"
done <<< "$LISTA"

echo "== Total de switches LAN en SIMON =="
psql -h 127.0.0.1 -U monitoreo -d monitoreo -c \
  "SELECT count(*) AS switches FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='switch_lan'"
