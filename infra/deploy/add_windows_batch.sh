#!/usr/bin/env bash
# Agrega varios servidores Windows por SNMP (perfil hostresources). Env: U/PASS, COMM, IPS.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
A="https://127.0.0.1/api"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"

T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "${U:-}" "${PASS:-}")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
TIPO=$($Pt "SELECT id FROM tipos_recurso WHERE codigo='servidor' LIMIT 1")
SITIO=$($Pt "SELECT id FROM sitios WHERE nombre ILIKE '%${SITIO_NOMBRE:-Nivel Central}%' LIMIT 1")
[ -z "$SITIO" ] && SITIO=null

for IP in $IPS; do
  echo "=== $IP ==="
  if [ -n "$($Pt "SELECT 1 FROM recursos WHERE hostname='$IP' LIMIT 1")" ]; then
    echo "  ya existe: $($Pt "SELECT nombre FROM recursos WHERE hostname='$IP' LIMIT 1")"
    continue
  fi
  NAME=$(snmpget -v2c -c "$COMM" -t 2 -r 1 -Oqv "$IP" 1.3.6.1.2.1.1.5.0 2>/dev/null | tr -d '"' | tr -d '\r')
  NOMBRE="${NAME:-SRV-$IP}"
  echo "  sysName: ${NAME:-<sin respuesta SNMP>}  ->  nombre=$NOMBRE"
  body=$(printf '{"tipo_id":%s,"sitio_id":%s,"nombre":"%s","hostname":"%s","intervalo_segundos":60,"activo":true,"parametros":{"snmp_version":"2c","port":161,"perfil":"hostresources","interfaces":true},"secretos":{"snmp_community":"%s"}}' \
    "$TIPO" "$SITIO" "$NOMBRE" "$IP" "$COMM")
  printf "  crear -> "
  curl -sk -o /dev/null -w '%{http_code}\n' -X POST "$A/recursos" \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "$body"
  RID=$($Pt "SELECT id FROM recursos WHERE hostname='$IP' ORDER BY id DESC LIMIT 1")
  if [ -n "$NAME" ]; then
    ( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py "$RID" >/dev/null 2>&1 )
  else
    $P -c "UPDATE recursos SET activo=false WHERE id=$RID" >/dev/null
    echo "  sin SNMP -> en pausa"
  fi
done

echo "== Resumen servidores Windows =="
$P -c "SELECT nombre, hostname, activo, estado_actual FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='servidor' ORDER BY hostname"
echo "== CPU/mem recientes =="
$P -c "SELECT r.nombre, m.metrica, m.valor, m.unidad FROM metricas m JOIN recursos r ON r.id=m.recurso_id JOIN tipos_recurso t ON t.id=r.tipo_id WHERE t.codigo='servidor' AND m.metrica IN ('cpu','mem') AND m.ts > now() - interval '5 min' ORDER BY r.nombre, m.metrica"
