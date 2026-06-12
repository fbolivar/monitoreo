#!/usr/bin/env bash
# Prueba SNMP (v2c PNMC) en todos los switches de piso y reactiva los que responden.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
PY=/opt/monitoreo/monitor/.venv/bin/python

# Switches de piso = switch_lan cuyo hostname está en 192.168.10.40-60 (los onboarded),
# excluyendo SW-CORE-01 (.10.1). Tomamos todos los switch_lan en .10.4x/.10.5x.
mapfile -t ROWS < <($Pt "SELECT r.id||'|'||r.hostname||'|'||r.nombre||'|'||r.activo
                         FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id
                         WHERE t.codigo='switch_lan' AND r.hostname <> '192.168.10.1'
                         ORDER BY r.hostname")

echo "== Probando SNMP en ${#ROWS[@]} switches =="
REACT=()
for row in "${ROWS[@]}"; do
  IFS='|' read -r id ip nombre activo <<< "$row"
  name=$(snmpget -v2c -c PNMC -t 2 -r 1 "$ip" 1.3.6.1.2.1.1.5.0 2>/dev/null | sed -E 's/.*STRING:\s*"?([^"]*)"?.*/\1/')
  if [ -n "$name" ]; then
    echo "  OK   $ip  $nombre  -> sysName='$name' (activo=$activo)"
    REACT+=("$id")
  else
    echo "  ---  $ip  $nombre  -> SIN SNMP (activo=$activo)"
  fi
done

if [ ${#REACT[@]} -gt 0 ]; then
  IDS="${REACT[*]}"
  echo
  echo "== Reactivando y chequeando ${#REACT[@]} switches con SNMP =="
  $P -c "UPDATE recursos SET activo=true WHERE id IN ($(IFS=,; echo "${REACT[*]}"))" >/dev/null
  ( cd /opt/monitoreo/monitor && PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python /tmp/chequear_ids.py $IDS >/dev/null 2>&1 )
  sleep 1
fi

echo
echo "== Estado final de los switches de piso =="
$P -c "SELECT r.hostname, r.nombre, r.activo, r.estado_actual,
          (SELECT count(*) FROM interfaces WHERE recurso_id=r.id) AS ifaces
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id
       WHERE t.codigo='switch_lan' AND r.hostname <> '192.168.10.1'
       ORDER BY r.activo DESC, r.hostname"
