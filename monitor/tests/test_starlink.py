"""Tests del parseo PURO del status Starlink (sin gRPC)."""
from types import SimpleNamespace

from monitor.probes.starlink import parsear_status


def _status(**kw):
    base = dict(
        pop_ping_latency_ms=45.0,
        pop_ping_drop_rate=0.0,
        downlink_throughput_bps=150_000_000,
        uplink_throughput_bps=20_000_000,
        obstruction_stats=SimpleNamespace(fraction_obstructed=0.012),
        device_state=SimpleNamespace(uptime_s=86400),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_parseo_basico_up():
    muestras, estado, detalle = parsear_status(_status())
    d = {m.nombre: (m.valor, m.unidad) for m in muestras}
    assert estado == "up"
    assert d["latency"] == (45.0, "ms")
    assert d["loss"] == (0.0, "%")
    assert d["throughput_down"] == (150.0, "Mbps")
    assert d["throughput_up"] == (20.0, "Mbps")
    assert d["obstruccion"][1] == "%"
    assert round(d["obstruccion"][0], 1) == 1.2
    assert detalle["fuente"] == "grpc"
    assert detalle["uptime_s"] == 86400


def test_drop_total_es_down():
    _, estado, _ = parsear_status(_status(pop_ping_drop_rate=1.0))
    assert estado == "down"


def test_campos_ausentes_no_rompen():
    status = SimpleNamespace(pop_ping_latency_ms=30.0)  # sin el resto
    muestras, estado, _ = parsear_status(status)
    nombres = {m.nombre for m in muestras}
    assert "latency" in nombres
    assert estado == "up"  # sin drop_rate => no se considera caído
