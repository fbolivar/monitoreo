"""AIOps: correlación de alertas (#14) — agrupación PURA.

Agrupa incidencias abiertas que probablemente son el MISMO evento: misma sede
y dentro de una ventana de tiempo. Dentro del grupo elige la causa raíz probable
(la incidencia de un recurso del que dependen los demás, o la más antigua).
"""
from __future__ import annotations

from datetime import datetime, timedelta


def agrupar(incidencias: list[dict], ventana_seg: int) -> list[list[dict]]:
    """Agrupa por (sitio_id) las incidencias cuyo inicio cae dentro de `ventana_seg`
    de alguna ya presente en el grupo. `incidencias`: dicts con id, sitio_id,
    inicio (datetime), recurso_id, depende_de_id. Devuelve grupos de >= 2."""
    ventana = timedelta(seconds=ventana_seg)
    por_sitio: dict = {}
    for inc in sorted(incidencias, key=lambda i: i["inicio"]):
        por_sitio.setdefault(inc.get("sitio_id"), []).append(inc)

    grupos: list[list[dict]] = []
    for _sitio, items in por_sitio.items():
        actual: list[dict] = []
        ultimo_ts: datetime | None = None
        for inc in items:
            if actual and ultimo_ts and (inc["inicio"] - ultimo_ts) > ventana:
                if len(actual) >= 2:
                    grupos.append(actual)
                actual = []
            actual.append(inc)
            ultimo_ts = inc["inicio"]
        if len(actual) >= 2:
            grupos.append(actual)
    return grupos


def causa_raiz(grupo: list[dict]) -> dict:
    """Elige la causa raíz probable del grupo: la incidencia cuyo recurso es
    ancestro (depende_de) de otros del grupo; si no, la más antigua."""
    ids_recursos = {i.get("recurso_id") for i in grupo}
    # Un recurso del que otros dependen es candidato a causa.
    for inc in sorted(grupo, key=lambda i: i["inicio"]):
        depende = {i.get("depende_de_id") for i in grupo if i.get("depende_de_id")}
        if inc.get("recurso_id") in depende:
            return inc
    return min(grupo, key=lambda i: i["inicio"])
