"""Tests del formato de respaldo .pnnc (puro, sin red ni BD)."""
import pytest

from monitor.respaldo_pnnc import (
    MAGIA,
    PnncError,
    desempacar,
    empacar,
    leer_metadata,
    sha256_hex,
)

META = {
    "producto": "SIMON",
    "base_datos": "monitoreo",
    "formato_payload": "pgdump-custom",
    "cifrado": "none",
}


def test_roundtrip_empacar_desempacar():
    payload = b"\x00\x01PGDMP fake dump bytes \xff\xfe" * 100
    blob = empacar(payload, META)
    assert blob[: len(MAGIA)] == MAGIA
    meta, recuperado = desempacar(blob)
    assert recuperado == payload
    assert meta["base_datos"] == "monitoreo"
    assert meta["sha256"] == sha256_hex(payload)
    assert meta["tam_payload"] == len(payload)


def test_no_muta_meta_del_llamador():
    original = dict(META)
    empacar(b"abc", META)
    assert META == original  # empacar no debe añadir sha256/tam al dict original


def test_leer_metadata_sin_payload():
    blob = empacar(b"x" * 5000, META)
    meta = leer_metadata(blob)
    assert meta["tam_payload"] == 5000


def test_magia_invalida():
    with pytest.raises(PnncError):
        desempacar(b"NOPNNC" + b"\x00" * 20)


def test_integridad_detecta_corrupcion():
    blob = bytearray(empacar(b"payload integro 12345", META))
    blob[-1] ^= 0xFF  # corromper el último byte del payload
    with pytest.raises(PnncError, match="integridad"):
        desempacar(bytes(blob), verificar=True)
    # sin verificar, no lanza
    meta, _ = desempacar(bytes(blob), verificar=False)
    assert meta["producto"] == "SIMON"


def test_cabecera_truncada():
    blob = empacar(b"datos", META)
    with pytest.raises(PnncError):
        leer_metadata(blob[:6])
