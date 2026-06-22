#!/usr/bin/env bash
#
# Auto-export OFF-SITE del respaldo de SIMON.
#
# Toma el último volcado diario (/var/backups/monitoreo/*.dump), lo envuelve en el
# formato propio .pnnc (cifrado opcional con openssl) y lo EMPUJA a un destino
# remoto (rsync/scp) o a una ruta local (un montaje NFS/SMB ya montado). Pensado
# para un cron diario, después del backup local. Es un NO-OP si no está configurado.
#
# Configuración: /etc/simon/offsite.env  (ver offsite.env.example). chmod 600.
#
set -euo pipefail

CFG=/etc/simon/offsite.env
VENV=/opt/monitoreo/monitor/.venv/bin/python
DUMP_DIR=/var/backups/monitoreo
log() { echo "[$(date '+%F %T')] $*"; }

[ -f "$CFG" ] || { log "Sin $CFG: off-site no configurado (no-op)."; exit 0; }
# shellcheck disable=SC1090
source "$CFG"
METODO="${OFFSITE_METODO:-none}"
[ "$METODO" = "none" ] && { log "OFFSITE_METODO=none: deshabilitado (no-op)."; exit 0; }
[ -n "${OFFSITE_DEST:-}" ] || { log "ERROR: falta OFFSITE_DEST."; exit 1; }
[ -x "$VENV" ] || { log "ERROR: no encuentro el venv del worker: $VENV"; exit 1; }

# Guarda anti-fallo-silencioso: si el destino es un montaje (SMB/NFS) y NO está
# montado, abortar — si no, METODO=local escribiría en el disco LOCAL de SIMON
# (no off-site) sin avisar. Configurar OFFSITE_REQUIRE_MOUNT con la ruta del montaje.
if [ -n "${OFFSITE_REQUIRE_MOUNT:-}" ] && ! mountpoint -q "$OFFSITE_REQUIRE_MOUNT"; then
    log "ERROR: $OFFSITE_REQUIRE_MOUNT no está montado; aborto (no escribo local)."
    exit 1
fi

DUMP=$(ls -t "$DUMP_DIR"/*.dump 2>/dev/null | head -1 || true)
[ -n "$DUMP" ] || { log "ERROR: no hay .dump local en $DUMP_DIR que exportar."; exit 1; }

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

# 1) Cifrado opcional (recomendado: el archivo sale del edificio).
PAY="$DUMP"; CIFRADO=none
if [ -n "${OFFSITE_PASSPHRASE:-}" ]; then
    PNNC_PASS="$OFFSITE_PASSPHRASE" openssl enc -aes-256-cbc -pbkdf2 -salt \
        -in "$DUMP" -out "$WORK/pay.enc" -pass env:PNNC_PASS
    PAY="$WORK/pay.enc"; CIFRADO=aes-256-cbc-pbkdf2
fi

# 2) Envolver en .pnnc con el módulo canónico (mismo formato que la app).
TS=$(date +%Y%m%d_%H%M%S)
OUT="$WORK/simon_${TS}.pnnc"
cd /opt/monitoreo/monitor
"$VENV" - "$PAY" "$OUT" "$CIFRADO" "$(basename "$DUMP")" <<'PY'
import sys, socket, datetime
from monitor.respaldo_pnnc import empacar
pay, out, cifrado, dump = sys.argv[1:5]
meta = {
    "producto": "SIMON",
    "entidad": "Parques Nacionales Naturales de Colombia",
    "creado_en": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "servidor": socket.gethostname(),
    "base_datos": "monitoreo",
    "formato_payload": "pgdump-custom",
    "cifrado": cifrado,
    "origen": "auto-export off-site (cron)",
    "dump_origen": dump,
}
open(out, "wb").write(empacar(open(pay, "rb").read(), meta))
PY
SIZE=$(stat -c%s "$OUT")
log "Generado simon_${TS}.pnnc ($SIZE bytes, cifrado=$CIFRADO) desde $(basename "$DUMP"). Enviando por $METODO…"

# 3) Empujar al destino.
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
KEY="${OFFSITE_SSH_KEY:-/etc/simon/offsite_key}"
case "$METODO" in
    rsync)
        rsync -az -e "ssh -i $KEY $SSH_OPTS" "$OUT" "$OFFSITE_DEST" ;;
    scp)
        scp -q -i "$KEY" $SSH_OPTS "$OUT" "$OFFSITE_DEST" ;;
    local)  # OFFSITE_DEST = ruta local (montaje NFS/SMB ya montado, o prueba)
        mkdir -p "$OFFSITE_DEST" && cp "$OUT" "$OFFSITE_DEST/"
        # Retención local opcional (conserva los N más recientes).
        if [ "${OFFSITE_RETENER:-0}" -gt 0 ]; then
            ls -1t "$OFFSITE_DEST"/simon_*.pnnc 2>/dev/null | tail -n +"$((OFFSITE_RETENER + 1))" | xargs -r rm -f
        fi ;;
    *)
        log "ERROR: OFFSITE_METODO desconocido: $METODO (use rsync|scp|local|none)"; exit 1 ;;
esac

log "OK: respaldo off-site enviado a $OFFSITE_DEST (simon_${TS}.pnnc, cifrado=$CIFRADO)."
