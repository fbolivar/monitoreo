#!/usr/bin/env bash
# Descubre CPU/memoria de un Windows por SNMP (HOST-RESOURCES-MIB).
set -euo pipefail
IP="${1:?Falta IP}"; C="${2:?Falta community}"
command -v snmpget >/dev/null 2>&1 || { apt-get update -qq; apt-get install -y -qq snmp >/dev/null; }

echo "== Identidad (sysDescr / sysName / uptime) =="
snmpget -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.2.1.1.1.0 1.3.6.1.2.1.1.5.0 1.3.6.1.2.1.1.3.0 2>&1 | head -8

echo "== CPU por núcleo: hrProcessorLoad (1.3.6.1.2.1.25.3.3.1.2) =="
snmpwalk -v2c -c "$C" -t 4 -r 1 -Oqn "$IP" 1.3.6.1.2.1.25.3.3.1.2 2>&1 | head -20

echo "== RAM total: hrMemorySize KB (1.3.6.1.2.1.25.2.2.0) =="
snmpget -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.2.1.25.2.2.0 2>&1

echo "== hrStorage: descripciones (.3) =="
snmpwalk -v2c -c "$C" -t 4 -r 1 "$IP" 1.3.6.1.2.1.25.2.3.1.3 2>&1 | head -15
echo "== hrStorageAllocationUnits (.4) / Size (.5) / Used (.6) =="
echo "-- .4 unidades --"; snmpwalk -v2c -c "$C" -t 4 -r 1 -Oqn "$IP" 1.3.6.1.2.1.25.2.3.1.4 2>&1 | head -15
echo "-- .5 size --";     snmpwalk -v2c -c "$C" -t 4 -r 1 -Oqn "$IP" 1.3.6.1.2.1.25.2.3.1.5 2>&1 | head -15
echo "-- .6 used --";     snmpwalk -v2c -c "$C" -t 4 -r 1 -Oqn "$IP" 1.3.6.1.2.1.25.2.3.1.6 2>&1 | head -15
