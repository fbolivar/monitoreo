"""Generación de reportes de disponibilidad/SLA (lógica pura, sin BD ni red).

- `reporte_due`: ¿toca enviar según la periodicidad y el último envío?
- `generar_csv` / `generar_pdf`: arman el archivo a adjuntar.
- `kpis`: resumen agregado para el cuerpo del correo y el encabezado.

El PDF usa fpdf2 (puro Python). Si no está instalado, `generar_pdf` devuelve
None y el runner cae a CSV.
"""
from __future__ import annotations

from datetime import datetime

RANGO_SEGUNDOS = {"24h": 86400, "7d": 604800, "30d": 2592000}
RANGO_ETIQUETA = {"24h": "últimas 24 horas", "7d": "últimos 7 días", "30d": "últimos 30 días"}


def rango_segundos(rango: str) -> int:
    return RANGO_SEGUNDOS.get(rango, 604800)


def reporte_due(periodo: str, ultimo_envio: datetime | None, ahora: datetime) -> bool:
    """¿Debe enviarse ahora? (primer envío si nunca se mandó; si no, según el periodo)."""
    if ultimo_envio is None:
        return True
    if periodo == "diario":
        return ahora.date() > ultimo_envio.date()
    if periodo == "semanal":
        return (ahora - ultimo_envio).days >= 7
    # mensual: cambió el (año, mes)
    return (ahora.year, ahora.month) != (ultimo_envio.year, ultimo_envio.month)


def alcance_texto(filas: list[dict], tipo_id: int | None, sitio_id: int | None) -> str:
    """Describe el ALCANCE del informe para su encabezado (función pura).

    Un informe acotado (p. ej. el que se manda al proveedor con solo sus enlaces)
    debe decir qué cubre, si no el destinatario asume que son todos los recursos.
    Sin filtros -> 'Todos los recursos'. Con filtro, el nombre sale de las propias
    filas (todas comparten tipo/sitio porque la query ya vino filtrada).
    """
    if not tipo_id and not sitio_id:
        return "Todos los recursos"
    primera = filas[0] if filas else {}
    partes: list[str] = []
    if tipo_id:
        partes.append(str(primera.get("tipo_nombre") or "tipo filtrado"))
    if sitio_id:
        partes.append(str(primera.get("sitio_nombre") or "sitio filtrado"))
    return " · ".join(partes)


def kpis(filas: list[dict]) -> dict:
    """Resumen: nº de recursos, disponibilidad promedio y total de incidencias."""
    disp = [f["disponibilidad"] for f in filas if f.get("disponibilidad") is not None]
    promedio = round(sum(disp) / len(disp), 3) if disp else None
    incidencias = sum(int(f.get("incidencias") or 0) for f in filas)
    return {"recursos": len(filas), "disponibilidad_promedio": promedio, "incidencias": incidencias}


def _orden(filas: list[dict]) -> list[dict]:
    # Peor disponibilidad primero (los problemáticos arriba).
    return sorted(filas, key=lambda f: (f["disponibilidad"] if f.get("disponibilidad") is not None else 101.0))


def _fmt_disp(v) -> str:
    return f"{v:.3f}%" if v is not None else "sin datos"


# Las fuentes base de fpdf2 (Helvetica) solo cubren latin-1. Los acentos españoles
# (á,é,í,ó,ú,ñ) sí entran; el em-dash y las comillas tipográficas no -> se mapean.
_REEMPLAZOS = {"—": "-", "–": "-", "…": "...", "‘": "'",
               "’": "'", "“": '"', "”": '"', "•": "*", " ": " "}


def _latin1(texto: str) -> str:
    """Hace el texto seguro para las fuentes base de fpdf2 (latin-1)."""
    for k, v in _REEMPLAZOS.items():
        texto = texto.replace(k, v)
    return texto.encode("latin-1", "replace").decode("latin-1")


def generar_csv(filas: list[dict]) -> bytes:
    """CSV (UTF-8 con BOM) con la tabla de disponibilidad. Mismo orden que la UI."""
    cab = ["Recurso", "Tipo", "Sitio", "Estado", "Disponibilidad %",
           "Up", "Degradado", "Caido", "Desconocido", "Incidencias"]
    lineas = [cab]
    for f in _orden(filas):
        lineas.append([
            f.get("nombre", ""), f.get("tipo_nombre", ""), f.get("sitio_nombre") or "",
            f.get("estado_actual", ""),
            "" if f.get("disponibilidad") is None else f"{f['disponibilidad']:.3f}",
            f.get("up", 0), f.get("degraded", 0), f.get("down", 0),
            f.get("unknown", 0), f.get("incidencias", 0),
        ])
    cuerpo = "\r\n".join(
        ",".join(f'"{str(c).replace(chr(34), chr(34) * 2)}"' for c in fila) for fila in lineas
    )
    return ("﻿" + cuerpo).encode("utf-8")


def generar_pdf(filas: list[dict], titulo: str, periodo_txt: str,
                generado: str, resumen: dict) -> bytes | None:
    """PDF tabular con fpdf2. Devuelve None si fpdf2 no está disponible."""
    try:
        from fpdf import FPDF
    except ImportError:
        return None

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _latin1(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, _latin1(f"Periodo: {periodo_txt}  -  Generado: {generado}"),
             new_x="LMARGIN", new_y="NEXT")
    prom = resumen.get("disponibilidad_promedio")
    pdf.cell(0, 5, _latin1(f"Recursos: {resumen['recursos']}  -  "
                           f"Disponibilidad promedio: {_fmt_disp(prom)}  -  "
                           f"Incidencias en el periodo: {resumen['incidencias']}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    cols = [("Recurso", 70), ("Tipo", 38), ("Sitio", 45), ("Estado", 26),
            ("Disponib.", 28), ("Up", 16), ("Degr.", 16), ("Caido", 16), ("Incid.", 16)]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(232, 240, 233)
    pdf.set_text_color(20, 20, 20)
    for nombre, w in cols:
        pdf.cell(w, 7, _latin1(nombre), border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for f in _orden(filas):
        d = f.get("disponibilidad")
        # Color de la celda de disponibilidad según semáforo.
        if d is None:
            pdf.set_text_color(120, 120, 120)
        elif d >= 99.0:
            pdf.set_text_color(20, 120, 50)
        elif d >= 95.0:
            pdf.set_text_color(200, 140, 0)
        else:
            pdf.set_text_color(200, 30, 30)
        disp_txt = _fmt_disp(d)
        pdf.set_text_color(20, 20, 20)
        valores = [
            (str(f.get("nombre", ""))[:40], "L"),
            (str(f.get("tipo_nombre", ""))[:22], "L"),
            (str(f.get("sitio_nombre") or "—")[:26], "L"),
            (str(f.get("estado_actual", "")), "C"),
            (disp_txt, "R"),
            (str(f.get("up", 0)), "R"),
            (str(f.get("degraded", 0)), "R"),
            (str(f.get("down", 0)), "R"),
            (str(f.get("incidencias", 0)), "R"),
        ]
        for (texto, align), (_n, w) in zip(valores, cols):
            pdf.cell(w, 6, _latin1(texto), border=1, align=align)
        pdf.ln()

    salida = pdf.output()  # fpdf2 devuelve bytearray
    return bytes(salida)
