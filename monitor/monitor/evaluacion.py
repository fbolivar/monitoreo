"""Lógica PURA de evaluación de estado contra umbrales (sin tocar la BD).

Catálogo de estados: up | degraded | down | unknown (maintenance lo aplica el
runner). Severidad de incidencia: info | warning | critical.

Mapeo:
  - estado_base 'down'     -> estado 'down',     severidad 'critical'
  - estado_base 'unknown'  -> estado 'unknown',  severidad 'warning'
  - estado_base 'degraded' -> estado 'degraded' (severidad mínima 'warning';
      los umbrales pueden escalarla a 'critical'). Lo usan probes que detectan
      degradación propia, p. ej. FortiGate HA con un miembro caído.
  - estado_base 'up':
      * métrica supera umbral CRÍTICO  -> 'degraded', severidad 'critical'
      * métrica supera umbral WARNING  -> 'degraded', severidad 'warning'
      * ninguna supera                 -> 'up',       severidad None
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import reglas as reglas_mod
from .models import Regla, Umbral
from .probes.base import ResultadoProbe

OPERADORES = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

_SEVERIDAD = {None: 0, "info": 1, "warning": 2, "critical": 3}


@dataclass
class Evaluacion:
    estado: str                       # up | degraded | down | unknown
    severidad: str | None             # None | info | warning | critical
    motivos: list[str] = field(default_factory=list)


def _peor(a: str | None, b: str | None) -> str | None:
    return a if _SEVERIDAD[a] >= _SEVERIDAD[b] else b


def evaluar(resultado: ResultadoProbe, umbrales: list[Umbral],
            reglas: list[Regla] | None = None) -> Evaluacion:
    if resultado.estado_base == "unknown":
        motivo = resultado.detalle.get("motivo") or resultado.detalle.get("error") or "no evaluable"
        return Evaluacion("unknown", "warning", [motivo])

    if resultado.estado_base == "down":
        motivo = resultado.detalle.get("motivo") or resultado.detalle.get("error") or "sin respuesta"
        return Evaluacion("down", "critical", [motivo])

    # estado_base 'up' o 'degraded': aplicar umbrales sobre las métricas medidas.
    # Si el probe ya reporta 'degraded', partimos de severidad 'warning'.
    metricas = {m.nombre: m.valor for m in resultado.metricas}
    if resultado.estado_base == "degraded":
        peor_sev: str | None = "warning"
        motivos: list[str] = [resultado.detalle["motivo"]] if resultado.detalle.get("motivo") else []
    else:
        peor_sev = None
        motivos = []

    for u in umbrales:
        if u.metrica not in metricas:
            continue
        valor = metricas[u.metrica]
        op = OPERADORES.get(u.operador)
        if op is None:
            continue

        if u.valor_critical is not None and op(valor, u.valor_critical):
            peor_sev = _peor(peor_sev, "critical")
            motivos.append(f"{u.metrica}={valor} {u.operador} {u.valor_critical} (crítico)")
        elif u.valor_warning is not None and op(valor, u.valor_warning):
            peor_sev = _peor(peor_sev, "warning")
            motivos.append(f"{u.metrica}={valor} {u.operador} {u.valor_warning} (warning)")

    # Triggers compuestos (multi-condición). Cada regla que dispara aporta su
    # severidad; se queda la peor de umbrales + reglas.
    for severidad, descripcion in reglas_mod.evaluar_reglas(metricas, reglas or []):
        peor_sev = _peor(peor_sev, severidad)
        motivos.append(descripcion)

    if peor_sev in ("warning", "critical"):
        return Evaluacion("degraded", peor_sev, motivos)

    return Evaluacion("up", None, [])


# ── Máquina de estados SOFT/HARD (anti-falsos-positivos) ──────────────────
@dataclass
class Confirmacion:
    estado_hard: str           # estado confirmado tras la máquina
    estado_candidato: str      # candidato en curso (== hard si está estable)
    intentos: int              # confirmaciones acumuladas del candidato
    transicion: bool           # ¿cambió el estado_hard en este chequeo?


def confirmar_estado(prev_hard: str, prev_candidato: str, prev_intentos: int,
                     crudo: str, max_intentos: int, recovery_intentos: int = 1) -> Confirmacion:
    """Confirma un estado crudo contra el HARD previo (estilo Nagios SOFT/HARD).

    Un estado distinto al HARD actual es un "candidato" que debe repetirse
    `objetivo` chequeos consecutivos para consolidarse. La recuperación a 'up'
    usa `recovery_intentos` (típicamente 1 = inmediato); el resto, `max_intentos`.

    - Si el crudo coincide con el HARD actual: se cancela cualquier candidato.
    - Si difiere y repite el candidato anterior: incrementa el contador.
    - Si difiere y es un candidato nuevo: reinicia el contador a 1.
    - Al alcanzar el objetivo: el candidato se vuelve HARD (transición).
    """
    objetivo = recovery_intentos if crudo == "up" else max_intentos
    objetivo = max(1, objetivo)

    if crudo == prev_hard:
        return Confirmacion(prev_hard, prev_hard, 0, False)

    if crudo == prev_candidato and prev_candidato != prev_hard:
        intentos = prev_intentos + 1
    else:
        intentos = 1

    if intentos >= objetivo:
        return Confirmacion(crudo, crudo, 0, True)
    return Confirmacion(prev_hard, crudo, intentos, False)
