#!/bin/sh
# Auto-inicialización del Postgres de desarrollo.
# El entrypoint oficial de la imagen postgres ejecuta este script SOLO en el
# primer arranque (cuando el volumen de datos está vacío). Aplica las
# migraciones "up" en orden y luego el seed.
#
# Para re-ejecutar desde cero:  docker compose down -v && docker compose up -d
set -e

DB_DIR=/db
PSQL="psql -v ON_ERROR_STOP=1 --username $POSTGRES_USER --dbname $POSTGRES_DB"

echo ">> [initdb] Aplicando migraciones up..."
for f in "$DB_DIR"/migrations/*.up.sql; do
  echo "   - $f"
  # APP_CRYPTO_KEY queda disponible como variable psql :'app_crypto_key'
  $PSQL -v app_crypto_key="$APP_CRYPTO_KEY" -f "$f"
done

echo ">> [initdb] Aplicando seed..."
for f in "$DB_DIR"/seeds/*.sql; do
  echo "   - $f"
  $PSQL -v app_crypto_key="$APP_CRYPTO_KEY" -f "$f"
done

echo ">> [initdb] Listo."
