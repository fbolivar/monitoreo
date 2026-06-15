"""Probe ICMP (ping): mide RTT, pérdida y jitter. Para cualquier recurso con
IP/hostname. Mayor cobertura, mínimo costo.

Métricas emitidas: latency (avg RTT), loss (% pérdida), jitter (variación media
entre RTTs consecutivos), rtt_min, rtt_max. Útiles para distinguir "enlace
degradado" (pérdida/jitter) de "enlace caído" en WAN/Starlink (umbrales/reglas).
"""
from __future__ import annotations

from .base import Muestra, ResultadoProbe


def construir_muestras_icmp(avg_rtt: float, min_rtt: float, max_rtt: float,
                            jitter: float, loss_pct: float, alive: bool) -> list[Muestra]:
    """Arma las métricas ICMP (función pura, testeable sin red)."""
    muestras: list[Muestra] = [Muestra("loss", round(loss_pct, 1), "%")]
    if alive:
        muestras.insert(0, Muestra("latency", round(avg_rtt, 2), "ms"))
        muestras.append(Muestra("jitter", round(jitter, 2), "ms"))
        muestras.append(Muestra("rtt_min", round(min_rtt, 2), "ms"))
        muestras.append(Muestra("rtt_max", round(max_rtt, 2), "ms"))
    return muestras


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

        loss_pct = h.packet_loss * 100
        # icmplib expone jitter (variación media entre RTTs consecutivos); 0 si no aplica.
        jitter = getattr(h, "jitter", 0.0) or 0.0
        metricas = construir_muestras_icmp(
            h.avg_rtt, h.min_rtt, h.max_rtt, jitter, loss_pct, h.is_alive)
        detalle = {
            "host": host,
            "enviados": h.packets_sent,
            "recibidos": h.packets_received,
            "rtt_min": h.min_rtt,
            "rtt_max": h.max_rtt,
            "jitter": round(jitter, 2),
        }

        if h.is_alive:
            return ResultadoProbe(True, "up", round(h.avg_rtt, 2), metricas, detalle)

        detalle["motivo"] = "sin respuesta ICMP (100% pérdida)"
        return ResultadoProbe(False, "down", None, metricas, detalle)
