#!/usr/bin/env bash
# Prueba alcance (ping) y SNMP (snmpget sysUpTime) a los switches. Env: COMM (community).
set -uo pipefail
for ip in 192.168.10.1 192.168.10.41 192.168.10.46; do
  echo "=== $ip ==="
  if ping -c2 -W2 "$ip" >/dev/null 2>&1; then echo "  ping OK"; else echo "  ping FALLA (sin ruta/bloqueado)"; fi
  out=$(snmpget -v2c -c "$COMM" -t 2 -r 1 "$ip" 1.3.6.1.2.1.1.3.0 2>&1 | head -1)
  echo "  snmp: $out"
done
