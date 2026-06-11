#!/usr/bin/env bash
# Descubre OIDs de CPU/memoria en Dell OS9 (Force10, enterprise 6027).
set -euo pipefail
IP="${1:?Falta IP}"; C="${2:?Falta community}"
W() { snmpwalk -v2c -c "$C" -t 4 -r 1 -Oqn "$IP" "$1" 2>&1 | head -"${2:-25}"; }

echo "== DELL-NETWORKING-CHASSIS CPU util (6027.3.26.1.4.4) =="
W 1.3.6.1.4.1.6027.3.26.1.4.4 30
echo "== DELL-NETWORKING memoria (6027.3.26.1.4.4 incluye mem?) / processor (6027.3.26.1.4.3) =="
W 1.3.6.1.4.1.6027.3.26.1.4.3 20
echo "== F10-S-SERIES chSysProcessorUtil (6027.3.10.1.2.9) =="
W 1.3.6.1.4.1.6027.3.10.1.2.9 20
echo "== F10-S-SERIES chassis stats (6027.3.10.1.2) — vista amplia =="
W 1.3.6.1.4.1.6027.3.10.1.2 60
