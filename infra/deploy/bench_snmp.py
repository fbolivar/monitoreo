"""Diagnóstico del polling SNMP: ¿dónde está el cuello y cuánto paraleliza?

Mide, con el cliente SNMP actual:
  A) coste de construir 1 SnmpEngine,
  B) N chequeos SECUENCIALES (1 hebra, engine caliente) -> wall total,
  C) N chequeos CONCURRENTES (M hebras, engines calientes) -> wall total,
  speedup = B/C. Si speedup ~1, el GIL (pysnmp en Python puro) es el muro y las
  hebras no ayudan; si speedup >> 1, el paralelismo por hebras sí escala.

Uso (en el servidor):  PYTHONPATH=/opt/monitoreo/monitor .venv/bin/python bench_snmp.py [ids...]
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

    from pysnmp.hlapi.asyncio import SnmpEngine
    t = time.perf_counter()
    SnmpEngine()
    coste_engine = time.perf_counter() - t
    print(f"A) Construir 1 SnmpEngine: {coste_engine:.2f}s")

    recursos = [r for r in (repo.cargar_recurso(db, i) for i in ids) if r]
    if not recursos:
        print("Sin recursos válidos.")
        return 1

    def probar(r):
        t0 = time.perf_counter()
        try:
            res = _ejecutar_probe(db, settings, r)
            return (r.id, time.perf_counter() - t0, res.estado_base)
        except Exception as e:  # noqa: BLE001
            return (r.id, time.perf_counter() - t0, f"ERR {e}")

    # Calentamiento: cada hebra construye su engine una vez (no se mide).
    with cf.ThreadPoolExecutor(max_workers=min(20, len(recursos))) as ex:
        list(ex.map(probar, recursos))

    # B) SECUENCIAL (1 hebra, engine caliente).
    t = time.perf_counter()
    seq = [probar(r) for r in recursos]
    wall_seq = time.perf_counter() - t
    print(f"B) SECUENCIAL  {len(recursos)} chequeos: wall {wall_seq:.1f}s "
          f"(por-probe medio {wall_seq/len(recursos):.1f}s)")

    # C) CONCURRENTE (M hebras, engines calientes del calentamiento).
    ex = cf.ThreadPoolExecutor(max_workers=min(20, len(recursos)))
    t = time.perf_counter()
    con = sorted(ex.map(probar, recursos))
    wall_con = time.perf_counter() - t
    ex.shutdown(wait=True)
    print(f"C) CONCURRENTE {len(recursos)} chequeos: wall {wall_con:.1f}s "
          f"(por-probe max {max(c[1] for c in con):.1f}s)")

    print(f"\n>> speedup hebras = B/C = {wall_seq/wall_con:.2f}x "
          f"(={'el GIL es el muro' if wall_seq/wall_con < 1.6 else 'las hebras escalan'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
