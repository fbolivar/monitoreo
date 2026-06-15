"""Estructuras de datos del dominio del worker."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Recurso:
    id: int
    nombre: str
    hostname: str | None
    tipo_codigo: str
    protocolo_default: str
    parametros: dict[str, Any] = field(default_factory=dict)
    intervalo_segundos: int = 60
    estado_actual: str = "unknown"
    sitio_id: int | None = None
    depende_de_id: int | None = None
    # Estados SOFT/HARD (ver evaluacion.confirmar_estado).
    estado_hard: str = "unknown"
    estado_candidato: str = "unknown"
    intentos_estado: int = 0
    max_check_attempts: int | None = None  # None => default global del worker


@dataclass
class Umbral:
    metrica: str
    operador: str
    valor_warning: float | None
    valor_critical: float | None
    duracion_segundos: int = 0


@dataclass
class Regla:
    """Trigger compuesto: expresión booleana sobre varias métricas.

    `expresion` es un AST JSON (ver reglas.py): hojas {metrica, op, valor} y
    nodos {and:[...]}, {or:[...]}, {not:{...}}. Al cumplirse, aporta `severidad`.
    """
    id: int
    nombre: str
    expresion: dict[str, Any]
    severidad: str = "warning"
    duracion_segundos: int = 0
    descripcion: str | None = None


@dataclass
class Canal:
    id: int
    tipo: str            # email | telegram | webhook | sms | slack
    nombre: str
    config: dict[str, Any]          # no sensible (destinatarios, url, chat_id, min_severidad...)
    secretos: dict[str, Any] | None  # descifrado (token, smtp_pass...)
