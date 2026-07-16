#!/usr/bin/env bash
#
# Prueba REAL de restauración del último respaldo OFF-SITE.
#
#   verificar_restauracion.sh [carpeta_pnnc]     (por defecto /mnt/offsite)
#
# Un backup que nadie restaura NO es un backup: es una carpeta con archivos y una
# suposición. Esto lo demuestra cada mes de forma automática: coge el .pnnc más
# reciente del destino off-site (el que de verdad usarías en un desastre), verifica
# su integridad, lo descifra, lo RESTAURA a una base de datos temporal, valida el
# contenido y la borra. Si algo falla, avisa por el canal de notificaciones.
#
# NO toca la base de datos de producción: restaura sobre una BD scratch aparte.
#
set -uo pipefail   # sin -e: queremos capturar el fallo y avisar, no morir en silencio

PNNC_DIR="${1:-/mnt/offsite}"
SCRATCH="simon_restore_test"
VENV=/opt/monitoreo/monitor/.venv/bin/python
CFG=/etc/simon/offsite.env
ESTADO=/var/lib/simon/ultima_verificacion_restauracion

log() { echo "[$(date '+%F %T')] $*"; }

WORK=$(mktemp -d)
chmod 755 "$WORK"          # postgres debe poder leer el dump
limpiar() {
    su - postgres -c "dropdb --if-exists $SCRATCH" >/dev/null 2>&1
    rm -rf "$WORK"
}
trap limpiar EXIT

# Avisa por el canal de notificaciones reutilizando el motor del worker.
avisar() {
    ( cd /opt/monitoreo/monitor && "$VENV" - "$1" "$2" <<'PY' >/dev/null 2>&1
import sys
from monitor.config import cargar_settings
from monitor.db import Database
from monitor.notificaciones.motor import notificar_simple
s = cargar_settings(); db = Database(s)
notificar_simple(db, s, sys.argv[1], sys.argv[2], "critical")
db.close()
PY
    ) || true
}

fallar() {
    log "FALLO: $1"
    avisar "[SIMON] La verificacion de restauracion del respaldo FALLO" \
           "No se pudo restaurar el ultimo respaldo off-site.

Motivo: $1
Origen: ${PNNC:-$PNNC_DIR}
Servidor: $(hostname)

Un backup que no restaura no es un backup: revisar cuanto antes."
    mkdir -p "$(dirname "$ESTADO")"
    echo "$(date '+%F %T') FALLO: $1" > "$ESTADO"
    exit 1
}

# ── 1) El respaldo off-site más reciente ─────────────────────────────
if [ "$PNNC_DIR" = "/mnt/offsite" ] && ! mountpoint -q /mnt/offsite; then
    fallar "el destino off-site (/mnt/offsite) no esta montado"
fi
PNNC=$(ls -1t "$PNNC_DIR"/simon_*.pnnc 2>/dev/null | head -1)
[ -n "$PNNC" ] || fallar "no hay ningun .pnnc en $PNNC_DIR"
log "Respaldo a probar: $PNNC ($(stat -c%s "$PNNC") bytes)"

# ── 2) Integridad + extracción del payload (módulo canónico) ─────────
log "Verificando integridad (sha256) y extrayendo…"
CIFRADO=$(cd /opt/monitoreo/monitor && "$VENV" - "$PNNC" "$WORK/payload" <<'PY' 2>&1
import sys
from monitor.respaldo_pnnc import desempacar
meta, payload = desempacar(open(sys.argv[1], "rb").read(), verificar=True)
open(sys.argv[2], "wb").write(payload)
print(meta.get("cifrado", "none"))
PY
) || fallar "integridad o formato invalido: $CIFRADO"
log "Integridad OK (cifrado=$CIFRADO)"

# ── 3) Descifrado si aplica ──────────────────────────────────────────
DUMP="$WORK/payload"
if [ "$CIFRADO" != "none" ]; then
    # shellcheck disable=SC1090
    [ -f "$CFG" ] && source "$CFG"
    [ -n "${OFFSITE_PASSPHRASE:-}" ] || fallar "el respaldo esta cifrado y no hay OFFSITE_PASSPHRASE en $CFG"
    PNNC_PASS="$OFFSITE_PASSPHRASE" openssl enc -d -aes-256-cbc -pbkdf2 \
        -in "$WORK/payload" -out "$WORK/dump" -pass env:PNNC_PASS 2>/dev/null \
        || fallar "no se pudo descifrar (passphrase incorrecta?)"
    DUMP="$WORK/dump"
    log "Descifrado OK"
fi
chmod 644 "$DUMP"

# ── 4) Restaurar a una BD scratch (NUNCA sobre produccion) ───────────
log "Restaurando en la BD temporal '$SCRATCH'…"
su - postgres -c "dropdb --if-exists $SCRATCH" >/dev/null 2>&1
su - postgres -c "createdb $SCRATCH" || fallar "no se pudo crear la BD temporal"
ERR=$(su - postgres -c "pg_restore -d $SCRATCH --no-owner --no-privileges '$DUMP'" 2>&1)
# pg_restore avisa de detalles benignos (owners/extensiones); solo importa el resultado.

# ── 5) Validar el contenido restaurado ───────────────────────────────
TABLAS=$(su - postgres -c "psql -tAc \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\" $SCRATCH" 2>/dev/null | tr -d ' ')
RECURSOS=$(su - postgres -c "psql -tAc \"SELECT count(*) FROM recursos\" $SCRATCH" 2>/dev/null | tr -d ' ')
INCID=$(su - postgres -c "psql -tAc \"SELECT count(*) FROM incidencias\" $SCRATCH" 2>/dev/null | tr -d ' ')

# Referencia: la produccion viva. El respaldo debe parecerse, no ser identico
# (es de las 03:00) — por eso se exige >=90% de las tablas, no igualdad exacta.
export PGPASSWORD=$(grep -oP 'DB_PASSWORD=\K.*' /root/monitoreo-secrets.env 2>/dev/null)
TABLAS_PROD=$(psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null | tr -d ' ')

[ -n "$TABLAS" ] && [ "$TABLAS" -gt 0 ] 2>/dev/null || fallar "la BD restaurada no tiene tablas (pg_restore: ${ERR:0:200})"
[ -n "$RECURSOS" ] && [ "$RECURSOS" -gt 0 ] 2>/dev/null || fallar "la tabla 'recursos' quedo vacia tras restaurar"
if [ -n "$TABLAS_PROD" ] && [ "$TABLAS_PROD" -gt 0 ] 2>/dev/null; then
    MIN=$(( TABLAS_PROD * 9 / 10 ))
    [ "$TABLAS" -ge "$MIN" ] 2>/dev/null || fallar "solo $TABLAS de $TABLAS_PROD tablas restauradas (esperado >= $MIN)"
fi

log "OK: restauracion verificada -> $TABLAS tablas (prod: ${TABLAS_PROD:-?}), $RECURSOS recursos, $INCID incidencias"
mkdir -p "$(dirname "$ESTADO")"
echo "$(date '+%F %T') OK: $(basename "$PNNC") -> $TABLAS tablas, $RECURSOS recursos" > "$ESTADO"
log "BD temporal eliminada. El respaldo off-site ES restaurable."
