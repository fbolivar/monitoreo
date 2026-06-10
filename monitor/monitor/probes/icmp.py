"""Probe ICMP (ping): mide RTT y pérdida de paquetes. Para cualquier recurso
con IP/hostname. Mayor cobertura, mínimo costo."""
from __future__ import annotations

from .base import Muestra, ResultadoProbe


class IcmpProbe:
    nombre = "icmp"
    requiere_secretos = False

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        from icmplib import ping  # import diferido: dependencia opcional en tiempo de ejecución

        host = recurso.hostname
        if not host:
            return ResultadoProbe(False, "unknown", None, [], {"error": "recurso sin hostname/IP"})

        timeout = settings.probe_timeout_ms / 1000
        try:
            h = ping(
                host,
                count=settings.icmp_count,
                interval=0.2,
                timeout=timeout,
                privileged=settings.icmp_privileged,
            )
        except Exception as e:  # p.ej. resolución DNS o permisos
            return ResultadoProbe(False, "down", None,
                                  [Muestra("loss", 100.0, "%")],
                                  {"error": str(e), "host": host})

        loss_pct = round(h.packet_loss * 100, 1)
        metricas = [Muestra("loss", loss_pct, "%")]
        detalle = {
            "host": host,
            "enviados": h.packets_sent,
            "recibidos": h.packets_received,
            "rtt_min": h.min_rtt,
            "rtt_max": h.max_rtt,
        }

        if h.is_alive:
            metricas.insert(0, Muestra("latency", round(h.avg_rtt, 2), "ms"))
            return ResultadoProbe(True, "up", round(h.avg_rtt, 2), metricas, detalle)

        detalle["motivo"] = "sin respuesta ICMP (100% pérdida)"
        return ResultadoProbe(False, "down", None, metricas, detalle)
