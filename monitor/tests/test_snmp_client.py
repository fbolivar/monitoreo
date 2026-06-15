"""Tests del aislamiento por hebra del cliente SNMP (sin red ni pysnmp).

Validan que el event loop se reutiliza dentro de una hebra y que hebras distintas
obtienen loops distintos (base del polling paralelo: cada hebra, su propio
engine/loop, sin estado compartido entre hebras).
"""
import threading

from monitor.probes import snmp_client as sc


def test_loop_se_reutiliza_en_la_misma_hebra():
    l1 = sc._hebra_loop()
    l2 = sc._hebra_loop()
    assert l1 is l2
    assert not l1.is_closed()


def test_loop_se_recrea_si_estaba_cerrado():
    loop = sc._hebra_loop()
    loop.close()
    nuevo = sc._hebra_loop()
    assert nuevo is not loop
    assert not nuevo.is_closed()


def test_hebras_distintas_obtienen_loops_distintos():
    loops: dict[str, object] = {}

    def capturar(nombre: str) -> None:
        loops[nombre] = sc._hebra_loop()

    t1 = threading.Thread(target=capturar, args=("a",))
    t2 = threading.Thread(target=capturar, args=("b",))
    t1.start(); t1.join()
    t2.start(); t2.join()

    assert loops["a"] is not loops["b"]


def test_ejecutar_corre_en_el_loop_de_la_hebra():
    async def suma():
        return 2 + 3

    assert sc._ejecutar(suma()) == 5
    # Tras ejecutar, el loop sigue vivo y reutilizable.
    assert not sc._hebra_loop().is_closed()
