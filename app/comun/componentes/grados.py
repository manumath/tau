"""Lista y alta de grados académicos (la usan «Mi perfil» y la ficha académica de la administración).

Patrón HTMX: toda la sección se reemplaza (outerHTML) al agregar o quitar un grado. `url` es la
base de las rutas (POST `url` agrega, DELETE `url/<id>` quita) y `envoltura(id_, *contenido)`
arma el contenedor con ese id (una tarjeta del perfil o un bloque de la ventana).
"""
import fasthtml.common as fh
from fasthtml.common import Datalist, Div, Input, Li, Option, P, Select, Span, Ul
from monsterui.all import Button, ButtonT, TextPresets, UkIcon

from app.comun import academicos, paises
from app.comun.componentes.layout import mensaje_error


def seccion_grados(uid: int, url: str, id_: str, envoltura, errores=(), datos=None):
    datos = datos or {}
    lista = academicos.grados(uid)
    filas = [Li(Div(Span(academicos.texto_grado(g), cls="text-sm"),
                    Span(f" · {g['nivel_texto']}", cls=TextPresets.muted_sm) if g.get("titulo") else "",
                    cls="flex-1"),
                fh.Button(UkIcon("x", height=14, width=14), type="button", aria_label="Quitar grado",
                          title="Quitar grado", cls="p-1 rounded hover:bg-muted hover:text-red-600",
                          hx_delete=f"{url}/{g['id']}", hx_target=f"#{id_}", hx_swap="outerHTML",
                          hx_confirm="¿Quitar este grado?"),
                cls="flex items-start gap-2 py-1.5") for g in lista]
    lista_paises = f"{id_}-paises"
    formulario = fh.Form(
        mensaje_error(*errores),
        Div(Select(Option("Nivel…", value=""),
                   *[Option(nombre, value=k, selected=k == datos.get("nivel")) for k, (nombre, _) in
                     academicos.NIVELES.items()],
                   name="nivel", cls="uk-select", aria_label="Nivel del grado", required=True),
            Input(name="titulo", value=datos.get("titulo") or "", cls="uk-input sm:col-span-2",
                  placeholder="Título (p. ej., Doctor en Matemáticas)", aria_label="Título"),
            Input(name="institucion", value=datos.get("institucion") or "", cls="uk-input sm:col-span-2",
                  placeholder="Institución que lo otorgó", aria_label="Institución"),
            Input(name="pais", value=datos.get("pais") or "", cls="uk-input", placeholder="País",
                  aria_label="País", list=lista_paises),
            Input(name="anio", value=datos.get("anio") or "", cls="uk-input", placeholder="Año",
                  aria_label="Año", inputmode="numeric"),
            Button(UkIcon("plus", height=14, width=14), "Agregar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
            cls="grid grid-cols-1 sm:grid-cols-4 gap-2 items-center"),
        Datalist(*[Option(value=x) for x in paises.nombres()], id=lista_paises),
        hx_post=url, hx_target=f"#{id_}", hx_swap="outerHTML", cls="space-y-2 mt-3")
    # El alta, plegada cuando ya hay grados (PLAN.md §54); abierta si no hay ninguno o si hubo un error.
    return envoltura(
        id_,
        Ul(*filas, cls="divide-y divide-border") if filas else P("Sin grados registrados.", cls=TextPresets.muted_sm),
        fh.Details(fh.Summary("+ Agregar grado", cls="cursor-pointer text-sm font-medium text-primary mt-2"), formulario,
                   open=bool(errores) or not filas))
