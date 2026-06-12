#!/usr/bin/env bash
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
$P -c "DELETE FROM recursos WHERE id=31"
echo "Switches de PISO1 tras limpieza:"
$P -c "SELECT id, nombre, hostname, estado_actual FROM recursos WHERE hostname IN ('192.168.10.41','192.168.10.46') ORDER BY nombre"
