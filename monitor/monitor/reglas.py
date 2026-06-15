"""Evaluador PURO de triggers compuestos (reglas multi-condición).

Una regla lleva una `expresion` (AST JSON) que se evalúa contra las métricas
medidas del chequeo. Si la expresión es verdadera, la regla "dispara" y aporta
su severidad a la evaluación (estilo expresiones de Zabbix).

Gramática del AST (sin texto a evaluar; NO se usa eval()):
    hoja:  {"metrica": "cpu", "op": ">", "valor": 90}
    nodo:  {"and": [expr, expr, ...]}
           {"or":  [expr, expr, ...]}
           {"not": expr}

Semántica de "métrica ausente": una hoja cuya métrica no se midió en este ciclo
devuelve None ("indeterminado"), que se propaga con lógica trivaluada para evitar
falsas alarmas: una regla SOLO dispara si su expresión evalúa exactamente True.
"""
from __future__ import annotations

from typing import Any

from .models import Regla

# Mismos operadores que evaluacion.py (umbrales clásicos).
_OPERADORES = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _eval(expr: Any, metricas: dict[str, float]) -> bool | None:
    """Evalúa un nodo del AST con lógica trivaluada (True/False/None)."""
    if not isinstance(expr, dict):
        return None

    if "and" in expr:
        hijos = [_eval(e, metricas) for e in expr["and"]]
        if any(h is False for h in hijos):
            return False
        if any(h is None for h in hijos):
            return None
        return True

    if "or" in expr:
        hijos = [_eval(e, metricas) for e in expr["or"]]
        if any(h is True for h in hijos):
            return True
        if any(h is None for h in hijos):
            return None
        return False

    if "not" in expr:
        h = _eval(expr["not"], metricas)
        return None if h is None else (not h)

    # Hoja: {metrica, op, valor}
    nombre = expr.get("metrica")
    op = _OPERADORES.get(expr.get("op", ">"))
    valor = expr.get("valor")
    if nombre is None or op is None or valor is None:
        return None
    if nombre not in metricas:
        return None
    try:
        return bool(op(metricas[nombre], float(valor)))
    except (TypeError, ValueError):
        return None


def dispara(regla: Regla, metricas: dict[str, float]) -> bool:
    """¿La regla dispara con estas métricas? (True solo si la expresión es True)."""
    return _eval(regla.expresion, metricas) is True


def evaluar_reglas(metricas: dict[str, float], reglas: list[Regla]) -> list[tuple[str, str]]:
    """Devuelve [(severidad, descripcion)] de las reglas que disparan."""
    disparadas: list[tuple[str, str]] = []
    for r in reglas:
        if dispara(r, metricas):
            disparadas.append((r.severidad, r.descripcion or f"regla '{r.nombre}'"))
    return disparadas


def validar_expresion(expr: Any, profundidad: int = 0) -> str | None:
    """Valida la forma del AST. Devuelve un mensaje de error o None si es válida.

    Reutilizable por la API (defensa en profundidad) además de la validación PHP.
    """
    if profundidad > 20:
        return "expresión demasiado anidada"
    if not isinstance(expr, dict):
        return "cada nodo debe ser un objeto"

    claves = {"and", "or", "not", "metrica"} & set(expr)
    if len(claves) != 1:
        return "cada nodo debe tener exactamente uno de: and, or, not, metrica"

    if "and" in expr or "or" in expr:
        hijos = expr["and"] if "and" in expr else expr["or"]
        if not isinstance(hijos, list) or not hijos:
            return "and/or requieren una lista no vacía"
        for h in hijos:
            err = validar_expresion(h, profundidad + 1)
            if err:
                return err
        return None

    if "not" in expr:
        return validar_expresion(expr["not"], profundidad + 1)

    # Hoja
    if not isinstance(expr.get("metrica"), str) or not expr["metrica"]:
        return "hoja sin 'metrica' válida"
    if expr.get("op", ">") not in _OPERADORES:
        return f"operador inválido: {expr.get('op')}"
    try:
        float(expr["valor"])
    except (KeyError, TypeError, ValueError):
        return "hoja sin 'valor' numérico"
    return None
