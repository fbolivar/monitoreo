#!/usr/bin/env bash
# Vuelca la respuesta cruda de ha-statistics del FortiGate para ver el campo
# que indica el primario. Uso: bash fw_raw.sh '<API_TOKEN>'
TOKEN="${1:?Falta token}"
H="Authorization: Bearer $TOKEN"
BASE="https://192.168.50.1:25443"
echo "== system/ha-statistics (crudo) =="
curl -sk "$BASE/api/v2/monitor/system/ha-statistics" -H "$H" | python3 -m json.tool
