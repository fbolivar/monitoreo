#!/usr/bin/env bash
# Agrega un servidor Windows por SNMP (perfil hostresources). Lee el nombre por SNMP.
# Env: U/PASS (admin), COMM (community), IP, SITIO_NOMBRE.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
A="https://127.0.0.1/api"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
IP="${IP:?falta IP}"

echo "== Probando SNMP en $IP =="
NAME=$(snmpget -v2c -c "$COMM" -t 2 -r 1 -Oqv "$IP" 1.3.6.1.2.1.1.5.0 2>/dev/null | tr -d '"' | tr -d '\r')
DESCR=$(snmpget -v2c -c "$COMM" -t 2 -r 1 -Oqv "$IP" 1.3.6.1.2.1.1.1.0 2>/dev/null | tr -d '"' | head -c 90)
echo "  sysName : ${NAME:-<sin respuesta SNMP>}"
echo "  sysDescr: ${DESCR:-<sin respuesta>}"

NOMBRE="${NAME:-SRV-$IP}"
TIPO=$($Pt "SELECT id FROM tipos_recurso WHERE codigo='servidor' LIMIT 1")
SITIO=$($Pt "SELECT id FROM sitios WHERE nombre ILIKE '%${SITIO_NOMBRE:-Nivel Central}%' LIMIT 1")
[ -z "$SITIO" ] && SITIO=null
echo "  nombre=$NOMBRE  tipo_servidor=$TIPO  sitio=$SITIO"

if [ -n "$($Pt "SELECT 1 FROM recursos WHERE hostname='$IP' LIMIT 1")" ]; then
  echo "  Ya existe un recurso con hostname $IP; se omite la creación."
else
  body=$(printf '{"tipo_id":%s,"sitio_id":%s,"nombre":"%s","hostname":"%s","intervalo_segundos":60,"activo":true,"parametros":{"snmp_version":"2c","port":161,"perfil":"hostresources","interfaces":true},"secretos":{"snmp_community":"%s"}}' \
    "$TIPO" "$SITIO" "$NOMBRE" "$IP" "$COMM")
  T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
    -d "$(printf '{"email":"%s","password":"%s"}' "${U:-}" "${PASS:-}")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
  printf "  crear %s -> " "$NOMBRE"
  curl -sk -o /dev/null -w '%{http_code}\n' -X POST "$A/recursos" \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "$body"
fi

RID=$($Pt "SELECT id FROM recursos WHERE hostname='$IP' ORDER BY id DESC LIMIT 1")

if [ -n "$NAME" ]; then
  echo "== Chequeo inmediato =="
  ( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py "$RID" 2>&1 | tail -1 )
  $P -c "SELECT nombre, estado_actual FROM recursos WHERE id=$RID"
  echo "== Métricas (CPU/mem) =="
  $P -c "SELECT metrica, valor, unidad FROM metricas WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 4"
  echo -n "puertos detectados: "; $Pt "SELECT count(*) FROM interfaces WHERE recurso_id=$RID"
else
  echo "== Sin SNMP: lo dejo en PAUSA para no alertar =="
  $P -c "UPDATE recursos SET activo=false WHERE id=$RID" >/dev/null
  echo "  habilita SNMP en el Windows ($IP) y luego reactivamos."
fi
