"""Forecasting de capacidad: regresión lineal PURA sobre una serie diaria.

Sin numpy (no añadir deps): mínimos cuadrados en Python plano. Proyecta cuántos
días faltan para que una métrica creciente (disco/mem en %) alcance un techo.

Todo aquí es función pura y testeable sin BD ni red.
"""
from __future__ import annotations

from dataclasses import dataclass

# Pendiente mínima (unidades/día) para considerar que algo "crece" de verdad.
_EPS_PENDIENTE = 1e-6


@dataclass
class Proyeccion:
    valor_actual: float
    pendiente_dia: float          # unidades por día
    r2: float | None              # bondad del ajuste [0..1] (None si no calculable)
    dias_restantes: float | None  # hasta el techo; None si estable/bajando


def regresion_lineal(valores: list[float]) -> tuple[float, float, float | None]:
    """Ajusta y = a*x + b sobre puntos (x=0..n-1, y=valores).

    Devuelve (pendiente, intercepto, r2). r2 es None si la varianza es nula
    (serie constante) o hay menos de 2 puntos.
    """
    n = len(valores)
    if n < 2:
        return 0.0, (valores[0] if valores else 0.0), None

    xs = list(range(n))
    sx = sum(xs)
    sy = sum(valores)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, valores))
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, sy / n, None

    pendiente = (n * sxy - sx * sy) / denom
    intercepto = (sy - pendiente * sx) / n

    # Coeficiente de determinación r².
    media = sy / n
    ss_tot = sum((y - media) ** 2 for y in valores)
    if ss_tot == 0:
        return pendiente, intercepto, None  # serie constante
    ss_res = sum((y - (pendiente * x + intercepto)) ** 2 for x, y in zip(xs, valores))
    r2 = 1.0 - ss_res / ss_tot
    return pendiente, intercepto, r2


def proyectar(valores: list[float], techo: float = 100.0) -> Proyeccion:
    """Proyecta los días hasta alcanzar `techo` desde el último valor observado.

    - Usa el ÚLTIMO valor real como punto de partida (no el ajustado), para que
      el conteo sea coherente con lo que se está midiendo ahora.
    - dias_restantes = None si la pendiente no es positiva (estable o bajando) o
      si ya se superó el techo se devuelve 0.
    """
    pendiente, _intercepto, r2 = regresion_lineal(valores)
    actual = valores[-1] if valores else 0.0

    if pendiente <= _EPS_PENDIENTE:
        return Proyeccion(actual, pendiente, r2, None)

    restante = techo - actual
    dias = 0.0 if restante <= 0 else restante / pendiente
    return Proyeccion(actual, pendiente, r2, dias)
