#!/usr/bin/env bash
# Verifica SNMP del Windows, lee sysName, renombra el recurso, reactiva y chequea. Env: COMM, IP.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
IP="${IP:?falta IP}"

echo "== Probando SNMP en $IP =="
NAME=$(snmpget -v2c -c "$COMM" -t 2 -r 1 -Oqv "$IP" 1.3.6.1.2.1.1.5.0 2>/dev/null | tr -d '"' | tr -d '\r')
echo "  sysName: ${NAME:-<sin respuesta>}"
RID=$($Pt "SELECT id FROM recursos WHERE hostname='$IP' ORDER BY id DESC LIMIT 1")
echo "  recurso id=$RID"

if [ -n "$NAME" ]; then
  $P -c "UPDATE recursos SET nombre='$NAME', activo=true WHERE id=$RID" >/dev/null
  echo "  renombrado a '$NAME' y reactivado."
  echo "== Chequeo inmediato =="
  ( cd /opt/monitoreo/monitor && .venv/bin/python /tmp/chequear_ids.py "$RID" 2>&1 | tail -1 )
  $P -c "SELECT nombre, hostname, estado_actual FROM recursos WHERE id=$RID"
  echo "== Métricas (CPU / memoria) =="
  $P -c "SELECT metrica, valor, unidad FROM metricas WHERE recurso_id=$RID ORDER BY ts DESC LIMIT 5"
  echo -n "interfaces detectadas: "; $Pt "SELECT count(*) FROM interfaces WHERE recurso_id=$RID"
else
  echo "  Aún no responde SNMP (revisa community/firewall/PermittedManagers)."
fi
