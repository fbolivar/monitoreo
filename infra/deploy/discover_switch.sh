#!/usr/bin/env bash
# Sondea un switch por SNMP v2c para confirmar acceso y descubrir OIDs de CPU/mem.
# Uso: bash discover_switch.sh <IP> <community>
set -euo pipefail
IP="${1:?Falta IP}"
C="${2:?Falta community}"
export DEBIAN_FRONTEND=noninteractive
command -v snmpget >/dev/null 2>&1 || apt-get install -y -qq snmp >/dev/null

OPTS="-v2c -c $C -t 4 -r 1 -O qvn"
echo "== Identidad (sysDescr / sysName / sysObjectID / uptime) =="
snmpget -v2c -c "$C" -t 4 -r 1 "$IP" \
  1.3.6.1.2.1.1.1.0 1.3.6.1.2.1.1.5.0 1.3.6.1.2.1.1.2.0 1.3.6.1.2.1.1.3.0 2>&1 | head -8

echo "== CPU candidato: HOST-RESOURCES hrProcessorLoad (1.3.6.1.2.1.25.3.3.1.2) =="
snmpwalk -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.2.1.25.3.3.1.2 2>&1 | head -10

echo "== Memoria candidato: HOST-RESOURCES hrStorage (descr/size/used) =="
echo "-- hrStorageDescr (.1.3.6.1.2.1.25.2.3.1.3) --"
snmpwalk -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.2.1.25.2.3.1.3 2>&1 | head -12
echo "-- hrStorageSize (.5) --"
snmpwalk -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.2.1.25.2.3.1.5 2>&1 | head -12
echo "-- hrStorageUsed (.6) --"
snmpwalk -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.2.1.25.2.3.1.6 2>&1 | head -12

echo "== CPU/mem Dell N/S-series (enterprise 674) — muestra =="
snmpwalk -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.4.1.674.10895.5000.2 2>&1 | grep -iE "cpu|mem|util|usage" | head -15 || echo "(sin coincidencias cpu/mem en 674)"
