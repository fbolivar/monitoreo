#!/usr/bin/env bash
# Prueba SNMP en los switches de piso; reactiva solo los que responden y fuerza
# un chequeo inmediato. Env: COMM (community SNMP).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"

echo "== Probando SNMP en los 14 switches =="
RESP=""
while IFS='|' read -r id ip nombre; do
  [ -z "$id" ] && continue
  if snmpget -v2c -c "$COMM" -t 2 -r 1 "$ip" 1.3.6.1.2.1.1.3.0 2>/dev/null | grep -q Timeticks; then
    $P -c "UPDATE recursos SET activo=true WHERE id=$id" >/dev/null
    RESP="$RESP $id"
    echo "  $nombre ($ip): RESPONDE -> reactivado"
  else
    echo "  $nombre ($ip): sin SNMP (sigue en pausa)"
  fi
done < <($Pt "SELECT id||'|'||hostname||'|'||nombre FROM recursos WHERE nombre LIKE 'SW-PISO%' ORDER BY nombre")

if [ -n "$RESP" ]; then
  echo "== Forzando chequeo inmediato de los reactivados =="
  ( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $RESP 2>&1 | tail -1 )
else
  echo "(ninguno respondió SNMP todavía)"
fi

echo "== Estado final =="
$P -c "SELECT nombre, activo, estado_actual FROM recursos WHERE nombre LIKE 'SW-PISO%' ORDER BY nombre"
echo "== Puertos detectados (de los activos) =="
$P -c "SELECT r.nombre, count(i.*) AS puertos FROM recursos r LEFT JOIN interfaces i ON i.recurso_id=r.id WHERE r.nombre LIKE 'SW-PISO%' AND r.activo GROUP BY r.nombre ORDER BY r.nombre"
