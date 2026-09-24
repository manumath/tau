"""Piezas visuales del perfil, compartidas por «Mi perfil» y el directorio."""
from fasthtml.common import A, Div, Img, P, Script, Span
from monsterui.all import Card, TextPresets, UkIcon

from app.identificadores import IDENTIFICADORES

# KaTeX: renderiza \( \), $ $ y $$ $$ en todo contenido nuevo (carga inicial y swaps de HTMX).
KATEX_CSS = "https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css"
KATEX_JS = """
import renderMathInElement from 'https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/contrib/auto-render.mjs';
const opciones = {
  delimiters: [
    {left: '$$', right: '$$', display: true},
    {left: '\\\\(', right: '\\\\)', display: false},
    {left: '$', right: '$', display: false},
  ],
  ignoredClasses: ['nomath'],
  throwOnError: false,
};
const render = el => renderMathInElement(el || document.body, opciones);
render(document.body);
document.addEventListener('htmx:load', e => render(e.detail.elt));
"""


def katex_headers():
    from fasthtml.common import Link
    return [Link(rel="stylesheet", href=KATEX_CSS), Script(KATEX_JS, type="module")]


def iniciales(nombres: str, apellidos: str) -> str:
    return (nombres[:1] + apellidos[:1]).upper()


def avatar(p: dict, tam: str = "size-24", texto: str = "text-2xl"):
    """Foto del investigador o, si no tiene, un círculo con sus iniciales."""
    if p.get("foto"):
        return Img(src=f"/fotos/{p['id']}?v={p['foto']}", alt=f"Foto de {p['nombres']} {p['apellidos']}",
                   cls=f"{tam} rounded-full object-cover border border-border shrink-0")
    return Div(iniciales(p["nombres"], p["apellidos"]), aria_hidden="true",
               cls=f"{tam} {texto} rounded-full bg-primary/15 text-primary font-semibold "
                   "flex items-center justify-center shrink-0 select-none")


def chip_msc(area: dict, *acciones, principal=False):
    return Span(
        UkIcon("star", height=12, width=12, cls="text-amber-500") if principal else "",
        Span(area["codigo"], cls="font-mono text-xs font-semibold nomath"),
        Span(area["texto"], cls="text-sm"),
        *acciones,
        title=area.get("texto_plano") or "",
        cls="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 "
            + ("bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800" if principal
               else "bg-muted/40"))


def lista_identificadores(p: dict):
    filas = []
    for campo, (etiqueta, _, enlace, _) in IDENTIFICADORES.items():
        valor = p.get(campo)
        if not valor:
            continue
        mostrado = valor.removeprefix("https://").removeprefix("http://")
        filas.append(Div(
            Span(etiqueta, cls=(TextPresets.muted_sm, "w-48 shrink-0")),
            A(mostrado, UkIcon("external-link", height=12, width=12, cls="ml-1"), href=enlace(valor),
              target="_blank", rel="noopener noreferrer",
              cls="text-primary hover:underline break-all inline-flex items-center nomath"),
            cls="flex flex-col sm:flex-row sm:items-center gap-1 py-1"))
    return Div(*filas) if filas else P("Sin identificadores registrados.", cls=TextPresets.muted_sm)


def texto_con_parrafos(texto: str | None, vacio: str = "Sin resumen de investigación."):
    """Separa en párrafos por líneas en blanco. El texto se escapa; KaTeX lo procesa en el cliente."""
    if not texto:
        return P(vacio, cls=TextPresets.muted_sm)
    parrafos = [p.strip() for p in texto.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return Div(*[P(p, cls="leading-relaxed whitespace-pre-line") for p in parrafos], cls="space-y-3")


def seccion(id_: str, titulo: str, *contenido, accion=None):
    """Tarjeta de sección con título y, opcionalmente, un botón de acción a la derecha."""
    return Card(
        Div(Span(titulo, cls="text-base font-semibold"), accion or "",
            cls="flex items-center justify-between gap-2 mb-3"),
        *contenido, id=id_)
