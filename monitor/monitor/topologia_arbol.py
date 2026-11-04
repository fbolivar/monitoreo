"""Derivación del árbol de dependencia a partir del grafo LLDP (lógica pura).

Las aristas LLDP son NO dirigidas (A ve a B). Para tener "causa raíz" hace falta
una dirección: hacia la(s) raíz(es) de la red (core/gateway). `construir_arbol`
hace un BFS desde las raíces sobre el grafo no dirigido y asigna a cada nodo su
PADRE = el vecino por el que se le descubrió (el más cercano a la raíz).

Raíces: las marcadas explícitamente (es_nucleo). Si un componente conexo no tiene
ninguna raíz marcada, se toma como raíz el nodo de MAYOR grado de ese componente
(heurística: el switch con más vecinos suele ser el de distribución/core).

Devuelve {recurso_id: padre_id | None}. Las raíces quedan con padre None.
"""
from __future__ import annotations

from collections import deque


def construir_arbol(aristas: list[tuple[int, int]], raices: set[int]) -> dict[int, int | None]:
    # Adyacencia no dirigida (sin auto-aristas ni duplicados).
    ady: dict[int, set[int]] = {}
    for a, b in aristas:
        if a == b:
            continue
        ady.setdefault(a, set()).add(b)
        ady.setdefault(b, set()).add(a)

    padres: dict[int, int | None] = {}
    visitados: set[int] = set()

    def bfs(origenes: list[int]) -> None:
        cola = deque()
        for r in origenes:
            if r in visitados:
                continue
            padres[r] = None
            visitados.add(r)
            cola.append(r)
        while cola:
            n = cola.popleft()
            for v in sorted(ady.get(n, ())):   # orden estable
                if v not in visitados:
                    visitados.add(v)
                    padres[v] = n
                    cola.append(v)

    # 1) BFS desde las raíces explícitas que existan en el grafo.
    bfs(sorted(r for r in raices if r in ady))

    # 2) Componentes sin raíz: raíz = nodo de mayor grado (desempata el id menor).
    nodos = set(ady)
    while True:
        faltan = nodos - visitados
        if not faltan:
            break
        raiz = max(faltan, key=lambda n: (len(ady[n]), -n))
        bfs([raiz])

    return padres
