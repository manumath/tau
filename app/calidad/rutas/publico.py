"""Página pública de indicadores de calidad (PLAN §57, etapa 9), sin sesión: ver `app/calidad/publico.py`."""
from fasthtml.common import A, APIRouter, Div, P, Span, Table, Tbody, Td, Th, Thead, Tr
from monsterui.all import H2, H3, Card, TextPresets

from app.calidad import publico
from app.calidad.rutas.indicadores import cifra, numero
from app.comun.componentes.publica import pagina_publica

rt = APIRouter()


def _celda(x, unidad):
    if x["oculta"]:
        return Span(f"n < {publico.MIN_BASE}", cls=TextPresets.muted_sm,
                    title=f"No se publica una cifra calculada sobre menos de {publico.MIN_BASE} personas o casos.")
    return Div(cifra(x, unidad, detalle=False),
               P(" · ".join(t for t in (f"n = {x['n']}" if x["n"] is not None else "",
                                       f"meta {numero(x['meta'])}" if x["meta"] is not None else "") if t),
                 cls="text-xs text-muted-foreground mt-1") if x["valor"] is not None else "")


def _tabla(d, anios):
    """En el teléfono, las cifras de cada año van debajo del indicador; desde `sm`, en sus columnas."""
    columna = "w-28 hidden sm:table-cell"
    return Table(
        Thead(Tr(Th("Indicador"), *[Th(str(a), cls=columna) for a in anios])),
        Tbody(*[Tr(Td(Div(Span(i["codigo"], cls="font-mono text-xs mr-2"), i["nombre"], cls="font-medium"),
                      P(i["formula"] or "", cls=TextPresets.muted_sm),
                      Div(*[Div(Span(str(a), cls="text-xs text-muted-foreground mr-2"),
                                _celda(i["cifras"][a], i["unidad_medida"]), cls="flex items-start")
                            for a in anios], cls="flex flex-wrap gap-x-6 gap-y-2 mt-2 sm:hidden")),
                   *[Td(_celda(i["cifras"][a], i["unidad_medida"]), cls=columna) for a in anios])
                for i in d["indicadores"]]),
        cls="uk-table uk-table-divider uk-table-small text-sm")


@rt("/publico/indicadores")
def get():
    x = publico.datos()
    if not x or not x["anios"] or not x["dimensiones"]:
        return pagina_publica("Indicadores de calidad", H2("Indicadores de calidad"),
                              P("Aún no hay indicadores publicados.", cls="mt-4"),
                              pie="Indicadores publicados por la Dirección de Carrera.")
    return pagina_publica(
        "Indicadores de calidad",
        H2(f"Indicadores de calidad · {x['unidad']['nombre']}"),
        P(f"{x['marco']['nombre']} · {x['anios'][0]}–{x['anios'][-1]}", cls=TextPresets.muted_sm),
        P("Cifras de los años que la Dirección de Carrera ya cerró: no cambian aunque después se corrijan los datos. "
          "Cada cifra muestra su base (n, por ejemplo cuántos estudiantes o respuestas) y la meta del año; el color dice si "
          f"la cumple. No se publica ninguna cifra calculada sobre menos de {publico.MIN_BASE} personas o casos.",
          cls="text-sm max-w-3xl my-4"),
        Div(*[Card(H3(Span(d["codigo"], cls="font-mono mr-2"), d["nombre"], cls="text-base font-semibold mb-3"),
                   _tabla(d, x["anios"])) for d in x["dimensiones"]], cls="space-y-6"),
        P(A("Perfiles de los investigadores", href="/publico/investigadores", cls="text-primary hover:underline"),
          cls="text-sm mt-8"),
        pie=f"{x['unidad']['nombre']} · Indicadores publicados por la Dirección de Carrera.")
