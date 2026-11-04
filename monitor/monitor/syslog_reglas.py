"""Evaluación PURA de reglas syslog patrón→incidencia (sin BD ni red).

`compilar` precompila los regex (y descarta los inválidos). `evaluar` aplica las
reglas compiladas a un evento ya parseado y devuelve las coincidencias (acciones a
ejecutar). El worker se encarga de abrir/cerrar la incidencia resultante.
"""
from __future__ import annotations

import re


def compilar(reglas: list[dict]) -> list[dict]:
    """Devuelve las reglas activas con su regex compilado en 'rx'. Omite patrones
    inválidos (no revientan el receptor)."""
    out = []
    for r in reglas:
        if not r.get("activo", True):
            continue
        try:
            rx = re.compile(r["patron"], re.IGNORECASE)
        except re.error:
            continue
        out.append({**r, "rx": rx})
    return out


def _campo(evento: dict, campo: str) -> str:
    return str(evento.get(campo) or "")


def evaluar(evento: dict, reglas_compiladas: list[dict]) -> list[dict]:
    """Reglas que casan con el evento. Cada resultado es la regla (con accion,
    severidad, clave, nombre, notificar). El orden preserva el de las reglas."""
    coincidencias = []
    for r in reglas_compiladas:
        texto = _campo(evento, r.get("campo", "mensaje"))
        if texto and r["rx"].search(texto):
            coincidencias.append(r)
    return coincidencias
