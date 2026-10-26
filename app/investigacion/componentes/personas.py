"""Selector de personas para formularios: autores de productos y participantes de actividades.

Cada persona elegida es un <li> con un input oculto `name=<campo>` y valor 'i:<id>' o 'e:<id>'.
En los autores, cada <li> lleva además un campo `filiacion` (selector en los del instituto, oculto
y vacío en los externos): las dos listas llegan paralelas, en el mismo orden.
El orden de los <li> es el orden de autoría; subir, bajar y quitar se hace en el navegador
(sin ida y vuelta al servidor). Agregar sí pasa por el servidor, que renderiza la fila.
"""
import json

import fasthtml.common as fh
from fasthtml.common import Div, Input, Li, Option, P, Select, Span, Ul
from monsterui.all import Button, ButtonT, TextPresets, UkIcon

from app.comun import estudiantes
from app.investigacion.actividades import ROLES
from app.investigacion.filiacion import OPCIONES as OPCIONES_FILIACION

CLS_ICONO = "p-1 rounded hover:bg-muted text-muted-foreground"
# En pantallas chicas, el selector (rol o filiación) baja a su propia línea con los botones a la derecha.
CLS_SELECTOR = "uk-select h-8 text-sm flex-1 min-w-0 sm:flex-none"


def ids(campo):
    return f"lista-{campo}", f"resultados-{campo}", f"buscar-{campo}"


def limpiar_tras_agregar(campo):
    """«buscador,resultados» que static/js/acciones.js vacía tras agregar a alguien (salvo si el
    servidor devolvió un error redirigido con HX-Retarget)."""
    _, resultados_id, buscar_id = ids(campo)
    return f"{buscar_id},{resultados_id}"


def selector_filiacion(p: dict, valor):
    """Autores: ¿firmó con la filiación del instituto? (oculto y vacío para externos)."""
    if not p["interno"]:
        return Input(type="hidden", name="filiacion", value="")
    actual = "" if valor is None else str(valor)
    return Select(*[Option(t, value=v, selected=v == actual) for v, t in OPCIONES_FILIACION.items()],
                  name="filiacion", aria_label=f"Filiación de {p['nombres']} {p['apellidos']}",
                  title="¿Firmó la publicación con la filiación del instituto (IIMAT, CMAT, FCPN o UMSA)?",
                  cls=f"{CLS_SELECTOR} sm:w-52" + (" border-amber-400 text-amber-700" if actual == "" else ""))


def fila(p: dict, campo: str, rol: str | None = None, filiacion=None):
    """Una persona elegida. Si `campo` es 'participante' incluye el selector de rol; si es
    'autor', el de filiación."""
    estudiante = estudiantes.etiqueta(p["id"]) if not p["interno"] and p.get("id") else None
    etiqueta = Span("Instituto" if p["interno"] else ("Externo · nuevo" if p.get("nueva") else estudiante or "Externo"),
                    cls="text-[10px] uppercase tracking-wide rounded px-1.5 py-0.5 "
                        + ("bg-primary/15 text-primary" if p["interno"] else "bg-muted"))
    selector_rol = Select(*[Option(t, value=v, selected=v == (rol or "asistente"))
                            for v, t in ROLES.items()],
                          name="rol", cls=f"{CLS_SELECTOR} sm:w-40",
                          aria_label=f"Rol de {p['nombres']} {p['apellidos']}") \
        if campo == "participante" else selector_filiacion(p, filiacion) if campo == "autor" else ""
    return Li(
        Input(type="hidden", name=campo, value=p["ref"]),
        Div(Div(Span(f"{p['nombres']} {p['apellidos']}", cls="font-medium"), etiqueta,
                cls="flex items-center gap-2"),
            P(p["afiliacion"] or "", cls=TextPresets.muted_sm) if p.get("afiliacion") else "",
            cls="min-w-0 basis-full sm:basis-auto sm:flex-1"),
        selector_rol,
        Div(fh.Button(UkIcon("chevron-up", height=14, width=14), type="button", cls=CLS_ICONO,
                      data_accion="subir", title="Subir", aria_label="Subir"),
            fh.Button(UkIcon("chevron-down", height=14, width=14), type="button", cls=CLS_ICONO,
                      data_accion="bajar", title="Bajar", aria_label="Bajar"),
            fh.Button(UkIcon("x", height=14, width=14), type="button", cls=CLS_ICONO + " hover:text-destructive",
                      data_accion="quitar", title="Quitar", aria_label="Quitar"),
            cls="flex shrink-0 ml-auto"),
        cls="flex flex-wrap sm:flex-nowrap items-center gap-x-3 gap-y-1.5 px-3 py-2")


def selector(campo: str, elegidas: list[dict], titulo: str, ayuda: str = ""):
    """Lista ordenable + buscador con autocompletar y alta rápida de externos."""
    lista_id, resultados_id, buscar_id = ids(campo)
    return Div(
        Div(Span(titulo, cls="uk-form-label"),
            Span(ayuda, cls=TextPresets.muted_sm) if ayuda else "", cls="flex flex-col"),
        Ul(*[fila(p, campo, p.get("rol"), p.get("filiacion")) for p in elegidas], id=lista_id,
           cls="rounded-md border border-border divide-y divide-border empty:hidden"),
        Div(Input(type="search", id=buscar_id, name="q", autocomplete="off",
                  placeholder="Buscar investigador o coautor externo por nombre…",
                  cls="uk-input", aria_label=f"Buscar {titulo.lower()}",
                  hx_get=f"/personas/buscar?campo={campo}", hx_target=f"#{resultados_id}",
                  hx_trigger="input changed delay:250ms, search",
                  hx_include=f"#{lista_id} input[name={campo}]",
                  # Enter no debe enviar el formulario principal.
                  data_enter="prevenir"),
            Div(id=resultados_id),
            cls="relative"),
        cls="space-y-2")


def resultados(campo: str, texto: str, encontradas: list[dict]):
    lista_id, resultados_id, _ = ids(campo)
    if len(texto.strip()) < 2:
        return ""
    opciones = [Li(fh.Button(
        Span(f"{p['nombres']} {p['apellidos']}", cls="font-medium"),
        Span(("Instituto" if p["interno"] else "Externo")
             + (f" · {p['afiliacion']}" if p.get("afiliacion") else ""), cls=TextPresets.muted_sm),
        type="button", cls="w-full text-left flex flex-col px-3 py-2 hover:bg-muted focus:bg-muted",
        hx_get=f"/personas/fila?campo={campo}&ref={p['ref']}", hx_target=f"#{lista_id}",
        hx_swap="beforeend", data_tras_pedido_limpiar=limpiar_tras_agregar(campo))) for p in encontradas]
    opciones.append(Li(fh.Button(
        UkIcon("user-plus", height=14, width=14), f"Registrar a «{texto.strip()}» como persona externa",
        type="button", cls="w-full text-left flex items-center gap-2 px-3 py-2 text-primary hover:bg-muted",
        hx_get="/personas/externo/nuevo", hx_vals=json.dumps({"campo": campo, "q": texto.strip()}),
        hx_target=f"#{resultados_id}")))
    return Ul(*opciones, cls="absolute z-30 w-full mt-1 max-h-72 overflow-y-auto rounded-md border "
                             "border-border bg-background shadow-lg divide-y divide-border")


def form_externo(campo: str, texto: str, errores=(), url: str | None = None, destino: str | None = None):
    """Mini formulario para registrar un externo. No es un <form> (estaría anidado): sus
    campos llevan prefijo ext_ y el botón los envía con hx-include.

    Por omisión agrega la persona como fila de la lista `campo`; con `url` y `destino` publica
    en otra ruta y reemplaza el contenido de `destino` (p. ej. participantes de un proyecto)."""
    lista_id, resultados_id, _ = ids(campo)
    partes = texto.strip().split()
    nombres, apellidos = (" ".join(partes[:-1]), partes[-1]) if len(partes) > 1 else (texto.strip(), "")
    bloque = f"externo-{campo}"
    return Div(
        P("Nueva persona externa", cls="font-medium text-sm"),
        *[P(e, cls="text-sm text-destructive") for e in errores],
        Div(Input(name="ext_nombres", value=nombres, placeholder="Nombres", cls="uk-input",
                  aria_label="Nombres"),
            Input(name="ext_apellidos", value=apellidos, placeholder="Apellidos", cls="uk-input",
                  aria_label="Apellidos"),
            Input(name="ext_institucion", placeholder="Institución", cls="uk-input",
                  aria_label="Institución"),
            Input(name="ext_pais", placeholder="País", cls="uk-input", aria_label="País"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-2"),
        Div(Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                   data_accion="vaciar", data_objetivo=resultados_id),
            Button("Agregar", type="button", cls=(ButtonT.primary, ButtonT.sm),
                   hx_include=f"#{bloque}",
                   **({"hx_post": url, "hx_target": destino} if url else
                      {"hx_post": f"/personas/externo?campo={campo}", "hx_target": f"#{lista_id}",
                       "hx_swap": "beforeend", "data_tras_pedido_limpiar": limpiar_tras_agregar(campo)})),
            cls="flex justify-end gap-2"),
        id=bloque,
        cls="absolute z-30 w-full mt-1 rounded-md border border-border bg-background shadow-lg p-3 space-y-2")
