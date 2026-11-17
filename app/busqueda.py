"""Búsqueda global (PLAN.md §48, paso 4): un campo en la barra de navegación busca a la vez en todo lo que los módulos
activos ofrecen (personas, productos, actividades, proyectos, asignaturas) y en las cuentas, para quien las administra.

Cada módulo **aporta** sus grupos (`BUSQUEDA` en `app/<paquete>/aportes.py`, PLAN §73): una función `(q, auth, límite)`
que respeta lo que la persona puede abrir (los proyectos, solo los que puede ver; las cuentas, solo con «ver_usuarios»).
Este archivo no importa de ningún paquete. Las sugerencias muestran pocos resultados por grupo; «Ver todos» (o Enter)
abre /buscar con más.
"""
from fasthtml.common import A, APIRouter, Div, H3, Li, P, Span, Ul
from monsterui.all import H2, TextPresets, UkIcon

from app.comun import modulos
from app.comun.componentes.layout import campo_busqueda, pagina

rt = APIRouter()
MINIMO = 2
EN_SUGERENCIAS, EN_PAGINA = 4, 30


def grupos_activos() -> list[tuple]:
    """(orden, título, icono, función) de los módulos activos, en su orden."""
    return sorted((g for aporte in modulos.aportes("busqueda") for g in aporte), key=lambda g: g[0])


def buscar(q: str, auth: dict, limite: int) -> list[dict]:
    """[{titulo, icono, items: [{texto, href, detalle}]}], solo los grupos con resultados."""
    if len(q.strip()) < MINIMO:
        return []
    grupos = [{"titulo": t, "icono": i, "items": f(q, auth, limite)} for _, t, i, f in grupos_activos()]
    return [g for g in grupos if g["items"]]


def _lista(palabras) -> str:
    """['personas', 'cuentas', 'productos'] → 'personas, cuentas y productos'."""
    return palabras[0] if len(palabras) == 1 else ", ".join(palabras[:-1]) + " y " + palabras[-1]


def _item(x):
    return Li(A(Span(x["texto"], cls="font-medium"),
                Span(x["detalle"], cls=TextPresets.muted_sm) if x["detalle"] else "",
                href=x["href"], cls="flex flex-col px-3 py-2 hover:bg-muted focus:bg-muted focus:outline-none"))


@rt("/buscar/sugerencias")
def get(auth, q: str = ""):
    """Lo que se despliega bajo el campo de la barra de navegación."""
    if len(q.strip()) < MINIMO:
        return ""
    grupos = buscar(q, auth, EN_SUGERENCIAS)
    cuerpo = [Div(P(g["titulo"], cls="px-3 pt-2 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground"),
                  Ul(*[_item(x) for x in g["items"]])) for g in grupos] or \
        [P("Sin resultados.", cls=(TextPresets.muted_sm, "px-3 py-2"))]
    return Div(*cuerpo,
               A(f"Ver todos los resultados de «{q.strip()}»", href=f"/buscar?q={q.strip()}",
                 cls="block px-3 py-2 text-sm text-primary hover:underline border-t border-border"),
               cls="absolute right-0 z-50 mt-1 w-[26rem] max-w-[90vw] max-h-[70vh] overflow-y-auto rounded-md border "
                   "border-border bg-background shadow-lg text-left", role="region", aria_label="Resultados de la búsqueda")


@rt("/buscar")
def get(auth, q: str = ""):
    grupos = buscar(q, auth, EN_PAGINA)
    resultados = [Div(H3(UkIcon(g["icono"], height=16, width=16), f"{g['titulo']} ({len(g['items'])})",
                         cls="flex items-center gap-2 text-base font-semibold mb-1"),
                      Ul(*[_item(x) for x in g["items"]], cls="divide-y divide-border rounded-md border border-border"),
                      cls="space-y-1") for g in grupos]
    return pagina(
        "Buscar",
        H2("Buscar"),
        Div(campo_busqueda(q, sugerencias=False), cls="max-w-xl my-4"),
        P("Escriba al menos dos letras: busca en " + _lista([t.lower() for _, t, _, _ in grupos_activos()]) + "."
          if len(q.strip()) < MINIMO else
          f"Sin resultados para «{q.strip()}»." if not grupos else
          f"Hasta {EN_PAGINA} resultados por grupo.", cls=(TextPresets.muted_sm, "mb-4")),
        Div(*resultados, cls="space-y-6"),
        usuario=auth)
