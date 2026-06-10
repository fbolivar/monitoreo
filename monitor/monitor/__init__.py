"""Workers de monitoreo de disponibilidad de TI.

Procesos headless que ejecutan chequeos (ICMP, HTTP/HTTPS, TCP) según el
intervalo configurado por recurso, evalúan el estado contra los umbrales,
y escriben en `chequeos`, `metricas` e `incidencias`.
"""

__version__ = "0.1.0"
