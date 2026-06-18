"""Calidad activa de enlaces WAN/Starlink (#4).

Mide latencia/jitter/pérdida (ICMP) y, si hay un servidor iperf3 configurado,
throughput de bajada/subida. Estima un **MOS** (Mean Opinion Score, 1.0–4.5) con
una versión simplificada del E-model de la UIT-T G.107 para traducir la red a
"calidad de voz percibida" — útil para reclamar SLA a un proveedor (Starlink).

Las funciones de cálculo son PURAS y testeables; la E/S (ping + iperf3) está
aislada en `medir`.
"""
from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess

log = logging.getLogger(__name__)


def mos_e_model(latency_ms: float, jitter_ms: float, loss_pct: float) -> float:
    """MOS estimado (1.00–4.50) a partir de latencia, jitter y pérdida.

    Simplificación del E-model (UIT-T G.107): latencia efectiva = oneway +
    2·jitter + 10 ms de de-jitter; factor R penalizado por retardo y por un
    deterioro por pérdida Ie-eff = 30·ln(1+15·Ppl) (G.711, muy sensible a pérdida)."""
    eff = (latency_ms / 2.0) + (jitter_ms * 2.0) + 10.0
    if eff < 160:
        r = 93.2 - (eff / 40.0)
    else:
        r = 93.2 - (eff - 120.0) / 10.0
    r -= 30.0 * math.log(1.0 + 15.0 * (max(0.0, loss_pct) / 100.0))
    if r < 0:
        return 1.0
    if r > 100:
        return 4.5
    mos = 1 + 0.035 * r + r * (r - 60) * (100 - r) * 7e-6
    return round(max(1.0, min(4.5, mos)), 2)


def clasificar(mos: float | None) -> str:
    """buena / aceptable / mala según el MOS."""
    if mos is None:
        return "mala"
    if mos >= 4.0:
        return "buena"
    if mos >= 3.0:
        return "aceptable"
    return "mala"


def resumir(latency_ms: float | None, jitter_ms: float | None, loss_pct: float,
            down_mbps: float | None, up_mbps: float | None) -> dict:
    """Arma el registro de calidad (puro)."""
    if latency_ms is None:
        mos = None
    else:
        mos = mos_e_model(latency_ms, jitter_ms or 0.0, loss_pct)
    return {
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        "jitter_ms": round(jitter_ms, 2) if jitter_ms is not None else None,
        "loss_pct": round(loss_pct, 2),
        "down_mbps": round(down_mbps, 2) if down_mbps is not None else None,
        "up_mbps": round(up_mbps, 2) if up_mbps is not None else None,
        "mos": mos,
        "calidad": clasificar(mos),
    }


def _iperf3(host: str, puerto: int, segundos: int, reverse: bool) -> float | None:
    """Throughput en Mbps con iperf3 (-J). reverse=True mide bajada (server→cliente)."""
    if not shutil.which("iperf3"):
        return None
    cmd = ["iperf3", "-c", host, "-p", str(puerto), "-t", str(segundos), "-J"]
    if reverse:
        cmd.append("-R")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=segundos + 15).stdout
        data = json.loads(out)
        bps = data.get("end", {}).get("sum_received", {}).get("bits_per_second")
        return round(bps / 1e6, 2) if bps else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError, KeyError):
        return None


def medir(host: str, settings, iperf_host: str | None = None,
          iperf_port: int = 5201, iperf_seg: int = 5) -> dict:
    """Mide calidad del enlace hacia `host`. Si hay iperf_host, añade throughput."""
    from icmplib import ping

    try:
        h = ping(host, count=max(10, settings.icmp_count), interval=0.2,
                 timeout=settings.probe_timeout_ms / 1000,
                 privileged=settings.icmp_privileged)
        latency = h.avg_rtt if h.is_alive else None
        jitter = getattr(h, "jitter", 0.0) or 0.0
        loss = h.packet_loss * 100
    except Exception as e:  # noqa: BLE001
        log.warning("WAN calidad: ping a %s falló: %s", host, e)
        latency, jitter, loss = None, None, 100.0

    down = up = None
    if iperf_host:
        down = _iperf3(iperf_host, iperf_port, iperf_seg, reverse=True)
        up = _iperf3(iperf_host, iperf_port, iperf_seg, reverse=False)

    return resumir(latency, jitter, loss, down, up)
