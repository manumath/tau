"""Piezas de la clasificación MSC2020: resultados del buscador (perfil y productos) y el selector
ordenable de los productos, donde el primer código es el principal."""
import fasthtml.common as fh
from fasthtml.common import Div, Input, Li, P, Span, Ul
from monsterui.all import TextPresets, UkIcon

from app.investigacion import msc
from app.investigacion.componentes.perfil import chip_msc

CLS_ICONO = "p-1 rounded hover:bg-muted text-muted-foreground"
LISTA, RESULTADOS, BUSCAR = "lista-msc", "resultados-msc", "buscar-msc"


def resultados(encontrados: list[dict], atributos, vacio="Sin resultados. Pruebe con otro término (el catálogo "
                                                          "MSC está en inglés)."):
    """Lista desplegable de códigos encontrados. `atributos(m)` da los hx-* del botón de cada uno."""
    if not encontrados:
        return Div(P(vacio, cls=(TextPresets.muted_sm, "p-3")),
                   cls="absolute z-30 w-full mt-1 rounded-md border border-border bg-background shadow-lg")
    secciones = {}

    def ruta_seccion(m):
        if m["nivel"] == 1:
            return ""
        s = secciones.setdefault(m["codigo"][:2], msc.seccion(m["codigo"]))
        return s["texto"] + " › " if s else ""

    return Ul(*[Li(fh.Button(
        Span(m["codigo"], cls="font-mono text-xs font-semibold w-14 shrink-0 nomath"),
        Span(Span(ruta_seccion(m), cls=TextPresets.muted_sm), m["texto"], cls="text-sm"),
        type="button", cls="w-full flex gap-3 items-baseline text-left px-3 py-2 "
                           "hover:bg-muted focus:bg-muted focus:outline-none",
        **atributos(m))) for m in encontrados],
        cls="absolute z-30 w-full mt-1 max-h-80 overflow-y-auto rounded-md border border-border "
            "bg-background shadow-lg divide-y divide-border", role="listbox")


def fila(m: dict):
    """Un código elegido en el formulario de productos: input oculto `msc` y botones subir, bajar y
    quitar (static/js/acciones.js). La marca «principal» la lleva el primero de la lista (CSS)."""
    return Li(
        Input(type="hidden", name="msc", value=m["codigo"]),
        Span(m["codigo"], cls="font-mono text-xs font-semibold w-14 shrink-0 nomath"),
        Span(m["texto"], cls="text-sm min-w-0 flex-1", title=m.get("texto_plano") or ""),
        Span(UkIcon("star", height=12, width=12), "Principal",
             cls="hidden group-first:inline-flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400 shrink-0"),
        Div(fh.Button(UkIcon("chevron-up", height=14, width=14), type="button", cls=CLS_ICONO,
                      data_accion="subir", title="Subir", aria_label=f"Subir {m['codigo']}"),
            fh.Button(UkIcon("chevron-down", height=14, width=14), type="button", cls=CLS_ICONO,
                      data_accion="bajar", title="Bajar", aria_label=f"Bajar {m['codigo']}"),
            fh.Button(UkIcon("x", height=14, width=14), type="button", cls=CLS_ICONO + " hover:text-red-600",
                      data_accion="quitar", title="Quitar", aria_label=f"Quitar {m['codigo']}"),
            cls="flex shrink-0"),
        cls="group flex items-center gap-3 px-3 py-2")


def selector(elegidos: list[dict], origen: str = ""):
    """Clasificación MSC2020 del producto: lista ordenable (el primero es el principal) y buscador.
    `origen`: de dónde salió una sugerencia (p. ej., «zbMATH Open»), para que se revise."""
    return Div(
        Div(Span("Clasificación MSC2020", cls="uk-form-label"),
            Span(f"El primero es el código principal; hasta {msc.MAX_PRODUCTO - 1} secundarios, de cualquier "
                 "nivel (11-XX, 11Mxx, 11M06). Los informes agrupan por la sección del principal.",
                 cls=TextPresets.muted_sm),
            Span(UkIcon("sparkles", height=12, width=12, cls="shrink-0"), f"Sugerida según {origen}: revísela.",
                 cls="inline-flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400")
            if origen and elegidos else "",
            cls="flex flex-col"),
        Ul(*[fila(m) for m in elegidos], id=LISTA,
           cls="rounded-md border border-border divide-y divide-border empty:hidden"),
        Div(Input(type="search", id=BUSCAR, name="msc_q", autocomplete="off",
                  placeholder="Agregar código: 11M, 11M06 o tema en inglés (zeta, graph coloring)…",
                  cls="uk-input", aria_label="Buscar código MSC",
                  hx_get="/productos/msc/buscar", hx_target=f"#{RESULTADOS}",
                  hx_trigger="input changed delay:250ms, search",
                  hx_include=f"#{LISTA}", data_enter="prevenir"),  # los input[name=msc] de la lista
            Div(id=RESULTADOS),
            cls="relative"),
        cls="space-y-2")


def chips(codigos: list[dict]):
    """Códigos de un producto como chips (el principal con estrella), para fichas."""
    return Div(*[chip_msc(m, principal=bool(m["principal"])) for m in codigos], cls="flex flex-wrap gap-2")
