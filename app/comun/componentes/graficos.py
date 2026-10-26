"""Gráficos de series en SVG hechos en el servidor: sin JavaScript ni recursos de otros sitios (la
CSP no los admite), se imprimen igual que en pantalla y cada barra puede enlazar a los registros
que la componen. Colores de la marca (app/comun/marca.py): van sobre la hoja blanca de los informes."""
from fasthtml import svg
from fasthtml.common import Div, Span

from app.comun import marca

COLORES = marca.GRAFICOS
_TEXTO, _EJE = "#52525b", "#d4d4d8"


def _formato(v) -> str:
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.1f}"
    return str(int(v))


def barras(titulo: str, etiquetas: list, series: list[tuple], enlaces: list[list] | None = None, nota: str = ""):
    """Barras apiladas: una por etiqueta (p. ej., el año), con el total encima.

    `series`: [(nombre, valores)] en el orden de apilado. `enlaces`: por serie, el href de cada
    barra (o None). Con una sola serie no se muestra leyenda."""
    ancho, alto, izq, abajo, arriba = 300, 150, 4, 22, 18
    n = max(len(etiquetas), 1)
    paso = (ancho - 2 * izq) / n
    barra = min(paso * 0.62, 40)
    totales = [sum(s[1][i] or 0 for s in series) for i in range(len(etiquetas))]
    maximo = max(totales, default=0) or 1
    escala = (alto - abajo - arriba) / maximo
    base = alto - abajo
    piezas = [svg.Line(x1=0, y1=base, x2=ancho, y2=base, stroke=_EJE, stroke_width=1)]
    for i, etiqueta in enumerate(etiquetas):
        x = izq + i * paso + (paso - barra) / 2
        y = base
        for j, (nombre, valores) in enumerate(series):
            v = valores[i] or 0
            if not v:
                continue
            h = v * escala
            y -= h
            rect = svg.Rect(width=round(barra, 1), height=round(h, 1), x=round(x, 1), y=round(y, 1),
                            fill=COLORES[j % len(COLORES)], rx=1.5)(svg.Title(f"{nombre}, {etiqueta}: {_formato(v)}"))
            href = enlaces[j][i] if enlaces and enlaces[j] else None
            piezas.append(svg.A(rect, href=href) if href else rect)
        centro = round(x + barra / 2, 1)
        piezas.append(svg.Text(_formato(totales[i]), x=centro, y=round(y - 4, 1), text_anchor="middle",
                               font_size=13, font_weight=600, fill="#18181b"))
        piezas.append(svg.Text(str(etiqueta), x=centro, y=alto - 5, text_anchor="middle", font_size=12.5, fill=_TEXTO))
    datos = "; ".join(f"{e}: {_formato(t)}" for e, t in zip(etiquetas, totales))
    # Muestras de color en SVG (no como fondo: Chrome omite los fondos al imprimir por omisión).
    muestra = lambda j: svg.Svg(svg.Rect(width=10, height=10, rx=2, fill=COLORES[j % len(COLORES)]),  # noqa: E731
                                viewBox="0 0 10 10", width=10, height=10, cls="mr-1 shrink-0", aria_hidden="true")
    leyenda = Div(*[Span(muestra(j), nombre, cls="inline-flex items-center")
                    for j, (nombre, _) in enumerate(series)],
                  cls="flex flex-wrap gap-x-3 gap-y-0.5 text-xs apagado") if len(series) > 1 else ""
    return Div(Div(titulo, cls="text-sm font-semibold"),
               svg.Svg(*piezas, viewBox=f"0 0 {ancho} {alto}", role="img", aria_label=f"{titulo}. {datos}",
                       cls="w-full h-auto"),
               leyenda, Div(nota, cls="apagado text-xs") if nota else "",
               cls="grafico border border-zinc-200 rounded p-3 space-y-1")
