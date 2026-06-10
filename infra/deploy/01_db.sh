#!/usr/bin/env bash
# FASE 6 · Paso BD: crea rol+base monitoreo, aplica migraciones y seeds.
# Genera DB_PASSWORD y APP_CRYPTO_KEY aleatorias y las guarda en
# /root/monitoreo-secrets.env (chmod 600). Recrea la BD de forma limpia
# (despliegue inicial: DROP + CREATE).
set -euo pipefail

REPO=/opt/monitoreo
SECRETS=/root/monitoreo-secrets.env

DB_PASS=$(openssl rand -hex 16)
APP_CRYPTO_KEY=$(openssl rand -hex 32)

echo "== (Re)crear rol y base =="
su postgres -c "psql -q -v ON_ERROR_STOP=1" <<SQL
DROP DATABASE IF EXISTS monitoreo;
DROP ROLE IF EXISTS monitoreo;
CREATE ROLE monitoreo LOGIN PASSWORD '${DB_PASS}';
CREATE DATABASE monitoreo OWNER monitoreo;
SQL
su postgres -c "psql -d monitoreo -q -c 'CREATE EXTENSION IF NOT EXISTS pgcrypto'"
echo "rol + base + pgcrypto OK"

export PGPASSWORD="$DB_PASS"
PSQL=(psql -h 127.0.0.1 -U monitoreo -d monitoreo -v ON_ERROR_STOP=1 -q)

echo "== Migraciones =="
"${PSQL[@]}" -f "$REPO/db/migrations/0001_init.up.sql";       echo "  0001 init OK"
"${PSQL[@]}" -f "$REPO/db/migrations/0002_timeseries.up.sql"; echo "  0002 timeseries OK"

echo "== Seeds =="
"${PSQL[@]}" -v app_crypto_key="$APP_CRYPTO_KEY" -f "$REPO/db/seeds/0001_seed.sql"; echo "  datos OK"
"${PSQL[@]}" -f "$REPO/db/seeds/0002_umbrales_snmp.sql";      echo "  umbrales snmp OK"
"${PSQL[@]}" -f "$REPO/db/seeds/0003_umbrales_starlink.sql";  echo "  umbrales starlink OK"
"${PSQL[@]}" -f "$REPO/db/seeds/0004_umbrales_fortigate.sql"; echo "  umbrales fortigate OK"

umask 077
printf 'DB_PASSWORD=%s\nAPP_CRYPTO_KEY=%s\n' "$DB_PASS" "$APP_CRYPTO_KEY" > "$SECRETS"

echo "== Verificación =="
echo -n "Tablas: ";    "${PSQL[@]}" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
echo -n "Recursos: ";  "${PSQL[@]}" -tAc "SELECT count(*) FROM recursos"
echo -n "Umbrales: ";  "${PSQL[@]}" -tAc "SELECT count(*) FROM umbrales"
echo "Recursos por tipo:"
"${PSQL[@]}" -c "SELECT t.codigo, count(*) AS n FROM recursos r JOIN tipos_recurso t ON t.id=r.tipo_id GROUP BY t.codigo ORDER BY t.codigo"
echo -n "Secreto FortiGate-DC-01 (descifrado): "
"${PSQL[@]}" -tAc "SELECT descifrar_secreto(secretos, '$APP_CRYPTO_KEY') FROM recursos WHERE nombre='FortiGate-DC-01'"

echo "== CLAVES GENERADAS (guardadas en $SECRETS) =="
cat "$SECRETS"
