"""Piezas para mostrar y elegir líneas de investigación institucionales."""
from fasthtml.common import Div, Input, Label, P, Span
from monsterui.all import TextPresets

from app.investigacion import lineas
from app.comun.componentes.registros import insignia


def insignias_lineas(lista: list[dict], fecha: str | None = None, vacio="Sin líneas de investigación."):
    """Una insignia por línea; las que ya no rigen (en `fecha`, hoy por omisión) van en gris."""
    if not lista:
        return P(vacio, cls=TextPresets.muted_sm)
    return Div(*[insignia(x["nombre"] + ("" if lineas.vigente(x, fecha) else " · ya no rige"),
                          "azul" if lineas.vigente(x, fecha) else "gris", icono="route")
                 for x in lista], cls="flex flex-wrap gap-2")


def casillas_lineas(elegidas: list[int], fecha: str | None = None, nombre="linea", actuales: list[dict] = ()):
    """Casillas con las líneas vigentes en `fecha` y, además, las ya adscritas (`actuales`) que
    dejaron de regir, marcadas como tales para que se puedan quitar."""
    opciones = lineas.vigentes(fecha)
    ids = {x["id"] for x in opciones}
    opciones += [x for x in actuales if x["id"] not in ids]
    if not opciones:
        return P("La administración aún no registra líneas de investigación vigentes.", cls=TextPresets.muted_sm)
    return Div(*[Label(Input(type="checkbox", name=nombre, value=str(x["id"]), checked=x["id"] in elegidas,
                             cls="uk-checkbox mt-0.5"),
                       Span(Span(x["nombre"], cls="text-sm"),
                            Span(" · ya no rige: desmárquela", cls="text-xs text-amber-700")
                            if x["id"] not in ids else "",
                            Span(x["descripcion"], cls=(TextPresets.muted_sm, "block"))
                            if x.get("descripcion") else ""),
                       cls="flex items-start gap-2")
                 for x in opciones], cls="grid grid-cols-1 sm:grid-cols-2 gap-2")
