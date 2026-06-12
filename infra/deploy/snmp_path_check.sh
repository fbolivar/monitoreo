#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
echo "== Recursos SNMP UP y su subred (para ver si cross-subnet SNMP funciona) =="
$P -c "SELECT r.nombre, r.hostname, t.codigo, r.estado_actual
       FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id
       WHERE r.activo AND r.estado_actual='up'
         AND t.codigo IN ('switch_lan','servidor','nas','ups')
       ORDER BY r.hostname"
echo
echo "== Prueba directa de SNMP a varios destinos (v2c PNMC) =="
for IP in 192.168.10.41 192.168.10.46 192.168.2.10 192.168.50.2; do
  R=$(snmpget -v2c -c PNMC -t 2 -r 1 "$IP" 1.3.6.1.2.1.1.5.0 2>&1 | head -1)
  echo "  $IP -> $R"
done
echo
echo "== ¿El puerto UDP/161 de .10.41 está abierto? (nmap si existe) =="
command -v nmap >/dev/null && nmap -sU -p161 --host-timeout 8s 192.168.10.41 2>&1 | grep -E "161|open|closed|filtered" || echo "  (nmap no instalado)"
