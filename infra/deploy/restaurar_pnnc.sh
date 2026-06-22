#!/usr/bin/env bash
#
# Restaura un respaldo .pnnc de SIMON (formato propio PNNC).
#
#   sudo bash restaurar_pnnc.sh <archivo.pnnc> [base_destino]
#
# DESTRUCTIVO: sobrescribe los datos de la base destino (por defecto 'monitoreo').
# Pasos: verifica la integridad (sha256) y extrae el payload con el módulo
# canónico (monitor/respaldo_pnnc.py), descifra si hace falta (openssl) y
# restaura con pg_restore. Pide confirmación explícita.
#
set -euo pipefail

PNNC="${1:?uso: restaurar_pnnc.sh <archivo.pnnc> [base_destino]}"
DBNAME="${2:-monitoreo}"
PY=/opt/monitoreo/monitor/.venv/bin/python
SECRETS=/root/monitoreo-secrets.env

[ -f "$PNNC" ]    || { echo "No existe el archivo: $PNNC" >&2; exit 1; }
[ -x "$PY" ]      || { echo "No encuentro el venv del worker: $PY" >&2; exit 1; }
[ -f "$SECRETS" ] || { echo "No encuentro $SECRETS (credenciales de BD)" >&2; exit 1; }
# shellcheck disable=SC1090
source "$SECRETS"

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

echo ">> Verificando integridad y extrayendo el payload…"
cd /opt/monitoreo/monitor
CIFRADO=$("$PY" - "$PNNC" "$WORK/payload" <<'PY'
import sys
from monitor.respaldo_pnnc import desempacar
meta, payload = desempacar(open(sys.argv[1], "rb").read(), verificar=True)
open(sys.argv[2], "wb").write(payload)
print(meta.get("cifrado", "none"))
PY
)
echo ">> Integridad OK."

DUMP="$WORK/payload"
if [ "$CIFRADO" != "none" ]; then
    echo ">> El respaldo está cifrado ($CIFRADO)."
    read -r -s -p "   Passphrase: " PNNC_PASS; echo
    export PNNC_PASS
    openssl enc -d -aes-256-cbc -pbkdf2 -in "$WORK/payload" -out "$WORK/dump" -pass env:PNNC_PASS
    unset PNNC_PASS
    DUMP="$WORK/dump"
fi

echo
echo ">> ADVERTENCIA: se RESTAURARÁ sobre la base '$DBNAME' (se sobrescriben datos)."
read -r -p "   Escribe 'RESTAURAR' para continuar: " OK
[ "$OK" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

export PGPASSWORD="$DB_PASSWORD"
pg_restore -h 127.0.0.1 -U "${DB_USER:-monitoreo}" -d "$DBNAME" \
    --clean --if-exists --no-owner --no-privileges "$DUMP"

echo ">> Restauración completada sobre '$DBNAME'."
