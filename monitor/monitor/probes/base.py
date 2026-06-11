"""Contratos comunes de los probes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Muestra:
    """Una métrica medida por un probe."""
    nombre: str          # 'latency', 'loss', 'http_status', 'ssl_dias_restantes'...
    valor: float
    unidad: str | None = None

    def as_tuple(self) -> tuple[str, float, str | None]:
        return (self.nombre, self.valor, self.unidad)


@dataclass
class ResultadoProbe:
    """Salida cruda de un probe (sin aplicar umbrales todavía)."""
    alcanzable: bool
    # Veredicto de conectividad: 'up' (responde), 'down' (no responde / no sano),
    # 'unknown' (no se pudo evaluar: config faltante o protocolo no soportado).
    estado_base: str
    latencia_ms: float | None
    metricas: list[Muestra] = field(default_factory=list)
    detalle: dict[str, Any] = field(default_factory=dict)
    # Snapshot de interfaces de red (IF-MIB), si el recurso lo tiene habilitado.
    interfaces: list[dict] | None = None

    def muestras_tuplas(self) -> list[tuple[str, float, str | None]]:
        return [m.as_tuple() for m in self.metricas]


class Probe(Protocol):
    nombre: str
    requiere_secretos: bool

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        ...
