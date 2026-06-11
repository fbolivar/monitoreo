#!/usr/bin/env bash
# Lote 1: traps->incidencias + dead-man's switch + filtro de sitios (worker).
# Despliega y prueba traps->incidencia con un recurso temporal (sin enviar correos).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h 127.0.0.1 -U monitoreo -d monitoreo"

cd /opt/monitoreo
git pull --ff-only origin main
git log --oneline -1

echo "== Reiniciar worker + receptor de traps =="
systemctl restart monitoreo-worker simon-traps
sleep 4
printf "  worker: "; systemctl is-active monitoreo-worker
printf "  traps:  "; systemctl is-active simon-traps

echo "== Prueba traps->incidencia (recurso temporal, correo desactivado) =="
$PSQL -c "UPDATE canales_notificacion SET activo=false WHERE tipo='email'" >/dev/null
TIPO=$($PSQL -tAc "SELECT id FROM tipos_recurso WHERE codigo='switch_lan' LIMIT 1")
RID=$($PSQL -tAc "INSERT INTO recursos (tipo_id, nombre, hostname, activo) VALUES ($TIPO,'ZZ-TRAP-TEST','127.0.0.1',true) RETURNING id")
$PSQL -c "INSERT INTO interfaces (recurso_id, if_index, if_name, admin_estado, oper_estado) VALUES ($RID,7,'Gi0/7','up','up') ON CONFLICT DO NOTHING" >/dev/null
echo "  recurso temporal id=$RID (hostname 127.0.0.1)"

echo "  -> enviando linkDown (ifIndex=7)…"
snmptrap -v2c -c public 127.0.0.1:162 '' 1.3.6.1.6.3.1.1.5.3 1.3.6.1.2.1.2.2.1.1.7 i 7 2>/dev/null || true
sleep 3
$PSQL -c "SELECT if_index, if_nombre, estado, titulo FROM incidencias WHERE recurso_id=$RID"

echo "  -> enviando linkUp (ifIndex=7)…"
snmptrap -v2c -c public 127.0.0.1:162 '' 1.3.6.1.6.3.1.1.5.4 1.3.6.1.2.1.2.2.1.1.7 i 7 2>/dev/null || true
sleep 3
$PSQL -c "SELECT if_index, estado, (resuelta_at IS NOT NULL) AS resuelta FROM incidencias WHERE recurso_id=$RID"

echo "== Limpieza =="
$PSQL -c "DELETE FROM recursos WHERE id=$RID" >/dev/null
$PSQL -c "UPDATE canales_notificacion SET activo=true WHERE tipo='email'" >/dev/null
echo "  recurso temporal eliminado, correo reactivado."

echo "== Dead-man's switch / filtro sitios =="
echo "  DEADMAN_URL: $(grep -E '^DEADMAN_URL=' /opt/monitoreo/monitor/.env 2>/dev/null | cut -d= -f2- || echo '(no configurada)')"
echo "  WORKER_SITIOS: $(grep -E '^WORKER_SITIOS=' /opt/monitoreo/monitor/.env 2>/dev/null | cut -d= -f2- || echo '(vacío = todos los sitios)')"
