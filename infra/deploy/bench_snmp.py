"""Micro-benchmark del polling SNMP: cuantifica el coste del SnmpEngine y mide
varios chequeos SNMP EN PARALELO con el cliente thread-local nuevo.

Uso (en el servidor, dentro de /opt/monitoreo/monitor con el venv):
    .venv/bin/python ../infra/deploy/bench_snmp.py 23 32 33 34 35 36 37 38

Sin argumentos usa una lista por defecto de switches/servidores.
"""
from __future__ import annotations

import concurrent.futures as cf
import sys
import time

from monitor.config import cargar_settings
from monitor.db import Database
from monitor import repository as repo
from monitor.runner import _ejecutar_probe


def main() -> int:
    ids = [int(x) for x in sys.argv[1:]] or [23, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45]
    settings = cargar_settings()
    db = Database(settings)

    # 1) Coste de construir UN SnmpEngine (lo que antes se pagaba por operación).
    from pysnmp.hlapi.asyncio import SnmpEngine
    t = time.perf_counter()
    SnmpEngine()
    coste_engine = time.perf_counter() - t
    print(f"Construir 1 SnmpEngine: {coste_engine:.2f}s "
          f"(antes ~7 por chequeo -> ~{7 * coste_engine:.1f}s de CPU desperdiciada/chequeo)")

    recursos = [r for r in (repo.cargar_recurso(db, i) for i in ids) if r]
    if not recursos:
        print("Sin recursos válidos.")
        return 1

    def probar(r):
        t0 = time.perf_counter()
        try:
            res = _ejecutar_probe(db, settings, r)
            return (r.id, round(time.perf_counter() - t0, 1), res.estado_base)
        except Exception as e:  # noqa: BLE001
            return (r.id, round(time.perf_counter() - t0, 1), f"ERROR {e}")

    # 2) Dos rondas: la 1ª construye el engine por hebra (frío); la 2ª lo reutiliza (tibio).
    for ronda in ("FRIA (construye engine/hebra)", "TIBIA (engine reutilizado)"):
        t = time.perf_counter()
        with cf.ThreadPoolExecutor(max_workers=min(20, len(recursos))) as ex:
            out = sorted(ex.map(probar, recursos))
        total = time.perf_counter() - t
        pmax = max(o[1] for o in out)
        psum = sum(o[1] for o in out)
        print(f"\n[{ronda}] {len(recursos)} chequeos | wall total {total:.1f}s | "
              f"por-probe max {pmax:.1f}s | suma secuencial {psum:.1f}s | "
              f"speedup ~{psum / total:.1f}x")
        for rid, dt, est in out:
            print(f"  id {rid:>3}  {dt:>5.1f}s  {est}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
