"""Cumplimiento de configuración (#7) — evaluación PURA.

Valida el texto de la última config respaldada (config_respaldos) contra una
política: debe contener / no debe contener una subcadena, o casar una regex.
"""
from __future__ import annotations

import re


def evaluar_politica(config_texto: str, politica: dict) -> tuple[bool, str]:
    """Devuelve (cumple, detalle). `politica`: tipo, patron."""
    texto = config_texto or ""
    tipo = politica.get("tipo")
    patron = politica.get("patron", "")

    if tipo == "contiene":
        ok = patron in texto
        return ok, ("" if ok else f"No se encontró: «{patron}»")
    if tipo == "no_contiene":
        ok = patron not in texto
        return ok, ("" if ok else f"Presente (prohibido): «{patron}»")
    if tipo == "regex":
        try:
            ok = re.search(patron, texto, re.MULTILINE) is not None
        except re.error as e:
            return False, f"regex inválida: {e}"
        return ok, ("" if ok else f"No casa la regex: /{patron}/")
    return False, f"tipo de política no soportado: {tipo}"


def aplica(politica: dict, tipo_id: int | None) -> bool:
    """¿La política aplica a un recurso de este tipo? (null = todos)."""
    at = politica.get("aplica_tipo_id")
    return at is None or at == tipo_id
