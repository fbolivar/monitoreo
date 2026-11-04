"""Lógica pura de on-call y escalado multinivel (sin BD ni red).

- `indice_guardia`: dado el nº de participantes, la longitud de la rotación y el
  ancla de inicio, devuelve QUÉ participante está de guardia AHORA.
- `nivel_a_disparar`: dada una política (niveles con su espera en minutos) y los
  minutos transcurridos desde que se abrió la incidencia, devuelve el nivel que
  toca disparar (el más alto cuyo umbral ya pasó y que aún no se escaló), o None.
"""
from __future__ import annotations

from datetime import datetime


def indice_guardia(n_participantes: int, rotacion_dias: int,
                   inicio: datetime, ahora: datetime) -> int | None:
    """Índice (0..n-1) del participante de guardia ahora. None si no hay a quién.

    La rotación avanza un participante cada `rotacion_dias` desde `inicio`.
    """
    if n_participantes <= 0 or rotacion_dias <= 0:
        return None
    dias = (ahora - inicio).total_seconds() / 86400.0
    if dias < 0:
        periodos = 0
    else:
        periodos = int(dias // rotacion_dias)
    return periodos % n_participantes


def nivel_a_disparar(niveles: list[dict], minutos_desde_apertura: float,
                     nivel_ya: int) -> dict | None:
    """Nivel que corresponde disparar, o None.

    `niveles`: lista de dicts con al menos {'orden', 'espera_min'}. Se dispara el
    nivel de MAYOR orden cuyo `espera_min` ya se cumplió y cuyo `orden` > `nivel_ya`
    (no repetir lo ya escalado). Si varios vencieron a la vez, se salta al más alto
    (no tiene sentido spamear los intermedios, que ya van tarde).
    """
    candidato = None
    for n in sorted(niveles, key=lambda x: x["orden"]):
        if n["orden"] <= nivel_ya:
            continue
        if minutos_desde_apertura >= n["espera_min"]:
            candidato = n  # sigue subiendo mientras venzan
    return candidato
