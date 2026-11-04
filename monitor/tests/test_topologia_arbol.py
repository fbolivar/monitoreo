"""Tests del árbol de dependencia derivado del LLDP (BFS puro)."""
from monitor.topologia_arbol import construir_arbol


def test_arbol_desde_raiz_explicita():
    # core(1) — sw(2) — ap(3);  core(1) — sw(4)
    aristas = [(1, 2), (2, 3), (1, 4)]
    p = construir_arbol(aristas, raices={1})
    assert p[1] is None          # raíz
    assert p[2] == 1
    assert p[4] == 1
    assert p[3] == 2             # el AP cuelga del switch, no del core


def test_sin_raiz_usa_mayor_grado():
    # estrella: 10 conecta con 11,12,13 -> 10 es el de mayor grado -> raíz
    aristas = [(10, 11), (10, 12), (10, 13)]
    p = construir_arbol(aristas, raices=set())
    assert p[10] is None
    assert p[11] == 10 and p[12] == 10 and p[13] == 10


def test_dos_componentes_independientes():
    aristas = [(1, 2), (3, 4)]
    p = construir_arbol(aristas, raices={1})
    assert p[1] is None and p[2] == 1
    # el segundo componente no tiene raíz explícita -> raíz por grado (empate -> id menor)
    assert p[3] is None and p[4] == 3


def test_ignora_autoaristas_y_duplicados():
    p = construir_arbol([(1, 1), (1, 2), (2, 1)], raices={1})
    assert p[1] is None and p[2] == 1


def test_camino_lineal_ancestria():
    # 1-2-3-4-5 desde raíz 1: cada uno cuelga del anterior
    p = construir_arbol([(1, 2), (2, 3), (3, 4), (4, 5)], raices={1})
    assert p[5] == 4 and p[4] == 3 and p[3] == 2 and p[2] == 1
