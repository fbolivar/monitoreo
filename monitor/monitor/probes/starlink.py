"""Probe Starlink: consulta gRPC al dish (status, obstrucción, latencia,
throughput). Si no hay acceso al dish, hace fallback a ICMP del gateway.

El parseo del status (parsear_status) es PURO y testeable sin gRPC.
"""
from __future__ import annotations

import logging

from ..models import Recurso
from .base import Muestra, ResultadoProbe
from .icmp import IcmpProbe

log = logging.getLogger(__name__)

DISH_HOST_DEFECTO = "192.168.100.1"
DISH_PORT_DEFECTO = 9200


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parsear_status(status) -> tuple[list[Muestra], str, dict]:
    """Mapea el mensaje dish_get_status a métricas + estado_base + detalle.

    `status` es un objeto tipo protobuf (se accede por atributos); se acepta
    cualquier objeto con esos atributos (testeable con SimpleNamespace).
    """
    lat = _f(getattr(status, "pop_ping_latency_ms", None))
    drop = _f(getattr(status, "pop_ping_drop_rate", None))
    dl = _f(getattr(status, "downlink_throughput_bps", None))
    ul = _f(getattr(status, "uplink_throughput_bps", None))

    obstruction = getattr(status, "obstruction_stats", None)
    frac = _f(getattr(obstruction, "fraction_obstructed", None)) if obstruction is not None else None

    muestras: list[Muestra] = []
    if lat is not None:
        muestras.append(Muestra("latency", round(lat, 2), "ms"))
    if drop is not None:
        muestras.append(Muestra("loss", round(drop * 100, 2), "%"))
    if frac is not None:
        muestras.append(Muestra("obstruccion", round(frac * 100, 3), "%"))
    if dl is not None:
        muestras.append(Muestra("throughput_down", round(dl / 1_000_000, 2), "Mbps"))
    if ul is not None:
        muestras.append(Muestra("throughput_up", round(ul / 1_000_000, 2), "Mbps"))

    # Conectividad: pérdida total (drop>=1.0) => sin servicio.
    estado_base = "down" if (drop is not None and drop >= 1.0) else "up"

    detalle: dict = {"fuente": "grpc"}
    ds = getattr(status, "device_state", None)
    if ds is not None:
        detalle["uptime_s"] = getattr(ds, "uptime_s", None)
    return muestras, estado_base, detalle


class StarlinkProbe:
    nombre = "starlink"
    requiere_secretos = False

    def run(self, recurso: Recurso, secretos, settings) -> ResultadoProbe:
        from . import starlink_client

        params = recurso.parametros or {}
        host = params.get("grpc_host") or recurso.hostname or DISH_HOST_DEFECTO
        port = int(params.get("grpc_port", DISH_PORT_DEFECTO))
        timeout = params.get("timeout_ms", settings.probe_timeout_ms) / 1000

        try:
            status = starlink_client.obtener_status(host, port, timeout)
        except Exception as e:
            log.info("Starlink %s sin acceso gRPC (%s); fallback a ICMP.", recurso.id, e)
            return self._fallback_icmp(recurso, settings, motivo=str(e))

        muestras, estado_base, detalle = parsear_status(status)
        latencia = next((m.valor for m in muestras if m.nombre == "latency"), None)
        return ResultadoProbe(estado_base == "up", estado_base, latencia, muestras, detalle)

    def _fallback_icmp(self, recurso: Recurso, settings, motivo: str) -> ResultadoProbe:
        params = recurso.parametros or {}
        gateway = params.get("gateway") or recurso.hostname or DISH_HOST_DEFECTO

        shim = Recurso(
            id=recurso.id,
            nombre=recurso.nombre,
            hostname=gateway,
            tipo_codigo=recurso.tipo_codigo,
            protocolo_default="icmp",
            parametros={},
            intervalo_segundos=recurso.intervalo_segundos,
            sitio_id=recurso.sitio_id,
        )
        res = IcmpProbe().run(shim, None, settings)
        res.detalle["fuente"] = "icmp-fallback"
        res.detalle["motivo_fallback"] = motivo
        res.detalle["gateway"] = gateway
        return res
