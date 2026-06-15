"""Detección de anomalías por línea base estacional (umbral dinámico).

Compara el valor medido contra la banda "normal" de esa métrica para la
hora-del-día actual: media ± k·σ (con un piso absoluto). Solo se considera
anomalía la desviación HACIA ARRIBA (cpu/mem/latencia/loss altos = problema);
caer por debajo de lo normal no se alerta.

Todo aquí es función pura y testeable (la media/σ se calcula en SQL en prod,
pero `media_desviacion` queda disponible para tests y fallback).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Anomalia:
    metrica: str
    valor: float
    media: float
    banda: float          # umbral efectivo = max(k·σ, piso)
    z: float | None       # nº de desviaciones (None si σ=0)


def media_desviacion(valores: list[float]) -> tuple[float, float]:
    """Media y desviación típica MUESTRAL (n-1). σ=0 con <2 puntos o serie constante."""
    n = len(valores)
    if n == 0:
        return 0.0, 0.0
    media = sum(valores) / n
    if n < 2:
        return media, 0.0
    var = sum((v - media) ** 2 for v in valores) / (n - 1)
    return media, var ** 0.5


def evaluar_anomalia(metrica: str, valor: float, media: float, desviacion: float,
                     k: float, piso: float) -> Anomalia | None:
    """¿`valor` supera la banda normal (media + max(k·σ, piso))? -> Anomalia o None.

    El `piso` evita híper-sensibilidad cuando σ es muy pequeña (métrica estable):
    sin él, una métrica casi constante marcaría anomalía ante el mínimo cambio.
    """
    banda = max(k * desviacion, piso)
    if valor > media + banda:
        z = (valor - media) / desviacion if desviacion > 0 else None
        return Anomalia(metrica, valor, media, banda, z)
    return None
