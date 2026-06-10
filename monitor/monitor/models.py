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


@dataclass
class Umbral:
    metrica: str
    operador: str
    valor_warning: float | None
    valor_critical: float | None
    duracion_segundos: int = 0


@dataclass
class Canal:
    id: int
    tipo: str            # email | telegram | webhook | sms | slack
    nombre: str
    config: dict[str, Any]          # no sensible (destinatarios, url, chat_id, min_severidad...)
    secretos: dict[str, Any] | None  # descifrado (token, smtp_pass...)
