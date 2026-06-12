#!/usr/bin/env bash
# Pausa (activo=false) los switches de piso mientras se habilita SNMP, y resuelve
# las incidencias falsas de onboarding para frenar el spam de correos.
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

echo "== Pausando (activo=false) los switches de piso =="
$P -c "UPDATE recursos SET activo=false WHERE nombre LIKE 'SW-PISO%'"
sleep 3
echo "== Resolviendo incidencias falsas (onboarding) =="
$P -c "UPDATE incidencias SET estado='resuelta', resuelta_at=now()
       WHERE estado<>'resuelta'
         AND recurso_id IN (SELECT id FROM recursos WHERE nombre LIKE 'SW-PISO%')"
echo -n "incidencias abiertas restantes de estos switches: "
$P -tAc "SELECT count(*) FROM incidencias i JOIN recursos r ON r.id=i.recurso_id
         WHERE r.nombre LIKE 'SW-PISO%' AND i.estado<>'resuelta'"
echo "== Estado actual =="
$P -c "SELECT nombre, activo, estado_actual, depende_de_id FROM recursos WHERE nombre LIKE 'SW-PISO%' ORDER BY nombre"
