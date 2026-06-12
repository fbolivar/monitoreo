#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
IP=192.168.10.41
echo "== snmpget sysDescr/sysName (v2c, PNMC) =="
snmpget -v2c -c PNMC -t 3 -r 1 "$IP" 1.3.6.1.2.1.1.5.0 1.3.6.1.2.1.1.1.0 2>&1 | head -6
echo "== ping =="
ping -c 2 -W 2 "$IP" 2>&1 | tail -2
echo "== recurso en SIMON =="
$P -c "SELECT id, nombre, hostname, activo, estado_actual FROM recursos WHERE hostname='$IP' OR nombre ILIKE '%10.41%' OR nombre ILIKE '%PISO1%'"
