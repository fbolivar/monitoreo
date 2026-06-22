r"""Formato de respaldo propio **.pnnc** (Parques Nacionales Naturales de Colombia).

Un archivo `.pnnc` es un contenedor portable y autodescrito para un respaldo de
la BD de SIMON. Estructura binaria (big-endian):

    [0:8]      magia  = b"PNNCBK" + version_mayor(1B) + version_menor(1B)
    [8:12]     uint32 = longitud M de la metadata JSON
    [12:12+M]  metadata JSON (UTF-8)
    [12+M:]    payload (bytes del pg_dump -Fc, opcionalmente cifrado)

La metadata describe el contenido para poder restaurarlo sin adivinar:

    {
      "producto": "SIMON",
      "entidad": "Parques Nacionales Naturales de Colombia",
      "creado_en": "2026-06-22T14:00:00Z",
      "servidor": "BC360",
      "base_datos": "monitoreo",
      "formato_payload": "pgdump-custom",          # pg_dump -Fc
      "cifrado": "none" | "aes-256-cbc-pbkdf2",     # openssl enc compatible
      "sha256": "<hex del payload>",                # integridad
      "tam_payload": 12345,
      "app_version": "<git short sha>"
    }

El `sha256` es del payload tal cual queda en el archivo (ya cifrado si aplica),
para verificar integridad ANTES de descifrar/restaurar. El cifrado, cuando se
usa, es compatible con `openssl enc -aes-256-cbc -pbkdf2 -salt` (la crypto la
hace la CLI de openssl en generación y restauración, no este módulo) — así el
contenedor es interoperable entre la API (PHP) y la restauración por shell.

Este módulo es la implementación CANÓNICA del formato (PHP la refleja en
App\Support\RespaldoPnnc). Funciones puras y testeables sin red ni BD.
"""
from __future__ import annotations

import hashlib
import json
import struct

MAGIA = b"PNNCBK"
VERSION = (1, 0)
_CABECERA_FIJA = len(MAGIA) + 2 + 4  # magia + version(2) + uint32 longitud


class PnncError(Exception):
    """Contenedor .pnnc inválido o corrupto."""


def sha256_hex(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def empacar(payload: bytes, meta: dict) -> bytes:
    """Arma el contenedor .pnnc. Sella sha256/tam_payload en la metadata.

    `meta` se copia (no se muta el dict del llamador). El sha256 se calcula
    sobre el payload tal cual se guarda.
    """
    meta = dict(meta)
    meta["sha256"] = sha256_hex(payload)
    meta["tam_payload"] = len(payload)
    meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    cabecera = MAGIA + bytes(VERSION) + struct.pack(">I", len(meta_bytes))
    return cabecera + meta_bytes + payload


def leer_metadata(blob: bytes) -> dict:
    """Lee SOLO la metadata (sin copiar el payload). Valida magia y versión."""
    if len(blob) < _CABECERA_FIJA or blob[: len(MAGIA)] != MAGIA:
        raise PnncError("no es un archivo .pnnc (magia inválida)")
    mayor = blob[len(MAGIA)]
    if mayor != VERSION[0]:
        raise PnncError(f"versión .pnnc no soportada: {mayor}")
    (m,) = struct.unpack(">I", blob[len(MAGIA) + 2 : _CABECERA_FIJA])
    fin = _CABECERA_FIJA + m
    if len(blob) < fin:
        raise PnncError("cabecera truncada")
    try:
        return json.loads(blob[_CABECERA_FIJA:fin].decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise PnncError(f"metadata ilegible: {e}") from e


def desempacar(blob: bytes, verificar: bool = True) -> tuple[dict, bytes]:
    """Devuelve (metadata, payload). Si `verificar`, valida el sha256 del payload."""
    meta = leer_metadata(blob)
    (m,) = struct.unpack(">I", blob[len(MAGIA) + 2 : _CABECERA_FIJA])
    payload = blob[_CABECERA_FIJA + m :]
    if verificar:
        esperado = meta.get("sha256")
        real = sha256_hex(payload)
        if esperado and esperado != real:
            raise PnncError(f"integridad: sha256 no coincide (esperado {esperado}, real {real})")
    return meta, payload


# ── CLI: inspeccionar / verificar un .pnnc (la restauración va por shell) ─────
def _main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("inspect", "verify"):
        print("uso: python -m monitor.respaldo_pnnc inspect|verify <archivo.pnnc>")
        return 2
    with open(argv[2], "rb") as f:
        blob = f.read()
    try:
        if argv[1] == "inspect":
            meta = leer_metadata(blob)
            print(json.dumps(meta, indent=2, ensure_ascii=False))
        else:
            meta, _ = desempacar(blob, verificar=True)
            print(f"OK — integridad verificada (sha256 {meta.get('sha256','')[:16]}…)")
    except PnncError as e:
        print(f"INVÁLIDO: {e}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv))
