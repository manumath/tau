"""Endpoints del selector de personas (autocompletar, filas y alta rápida de externos)."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, HtmxResponseHeaders, Input, P, Response, Span, Thead, Tr
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, Table, Tbody, Td, TextPresets, Th, UkIcon

from app.comun import paises, personas
from app.investigacion.componentes import personas as ui
from app.comun.componentes.layout import pagina
from app.comun.db import auditar

rt = APIRouter()
CAMPOS = {"autor", "participante"}


def _rol_inicial(campo):
    return "expositor" if campo == "participante" else None


@rt("/personas/buscar")
def get(campo: str = "autor", q: str = "", autor: list[str] = None, participante: list[str] = None):
    if campo not in CAMPOS:
        return ""
    elegidas = set((autor if campo == "autor" else participante) or [])
    return ui.resultados(campo, q, personas.buscar(q, excluir=elegidas))


@rt("/personas/fila")
def get(campo: str = "autor", ref: str = ""):
    p = personas.por_ref(ref)
    if campo not in CAMPOS or not p:
        return ""
    return ui.fila(p, campo, _rol_inicial(campo))


@rt("/personas/externo/nuevo")
def get(campo: str = "autor", q: str = ""):
    return ui.form_externo(campo, q) if campo in CAMPOS else ""


@rt("/personas/externo")
def post(auth, campo: str = "autor", ext_nombres: str = "", ext_apellidos: str = "",
         ext_institucion: str = "", ext_pais: str = ""):
    if campo not in CAMPOS:
        return ""
    if not ext_nombres.strip() or not ext_apellidos.strip():
        # El botón apunta a la lista; el error vuelve al recuadro del formulario.
        _, resultados_id, _ = ui.ids(campo)
        return (ui.form_externo(campo, f"{ext_nombres} {ext_apellidos}",
                                ["Nombres y apellidos son obligatorios."]),
                HtmxResponseHeaders(retarget=f"#{resultados_id}", reswap="innerHTML"))
    # Si ya existe alguien con el mismo nombre se reutiliza, en lugar de duplicarlo.
    externo = personas.externo_similar(ext_nombres, ext_apellidos) or personas.crear_externo(
        ext_nombres, ext_apellidos, ext_institucion, ext_pais, auth["id"])
    return ui.fila(personas.por_ref(f"e:{externo['id']}"), campo, _rol_inicial(campo))


# --- Coautores externos: completar país e institución ------------------------------------------------------------

def _permitido(auth):
    return auth["es_investigador"] or auth["es_admin"]


def fila_externo(e):
    return Tr(
        Td(Div(f"{e['apellidos']}, {e['nombres']}", cls="font-medium"),
           Div(f"{e['n_productos']} productos · {e['n_actividades']} actividades · {e['n_proyectos']} proyectos",
               cls=TextPresets.muted_sm)),
        Td(fh.Form(Input(name="institucion", value=e["institucion"] or "", cls="uk-input h-8 text-sm",
                         placeholder="Institución", aria_label=f"Institución de {e['nombres']} {e['apellidos']}"),
                   Input(name="pais", value=e["pais"] or "", list="lista-paises", placeholder="País",
                         cls="uk-input h-8 text-sm w-40" + ("" if e["pais"] else " border-amber-400"),
                         aria_label=f"País de {e['nombres']} {e['apellidos']}"),
                   Button("Guardar", type="submit", cls=(ButtonT.ghost, ButtonT.sm)),
                   hx_put=f"/personas/externos/{e['id']}", hx_target=f"#externo-{e['id']}", hx_swap="outerHTML",
                   cls="flex flex-wrap gap-2 items-center")),
        id=f"externo-{e['id']}")


def tabla_externos(q="", sin_pais=True):
    lista = personas.externos(q, sin_pais)
    return Div(Table(Thead(Tr(Th("Persona"), Th("Institución y país"))),
                     Tbody(*[fila_externo(e) for e in lista]) if lista else
                     Tbody(Tr(Td("No hay personas que coincidan." if q or not sin_pais else
                                 "Todas las personas externas tienen país registrado.", colspan=2,
                                 cls=(TextPresets.muted_sm, "text-center py-6")))),
                     cls="uk-table-divider uk-table-middle"),
               id="tabla-externos", cls="overflow-x-auto")


@rt("/personas/externos")
def get(auth, q: str = "", sin_pais: bool = True, todos: bool = False):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    sin_pais = sin_pais and not todos
    n_sin = len(personas.externos(solo_sin_pais=True))
    return pagina(
        "Coautores externos",
        Div(Div(H2("Coautores y participantes externos"),
                P("Personas sin cuenta en el portal (coautores, participantes de actividades y proyectos). Su país sirve "
                  "para medir la colaboración internacional (IAC-CINDA 3.5.2). Al importar desde OpenAlex el país se "
                  "completa solo; aquí se completan los que falten.", cls=(TextPresets.muted_sm, "max-w-3xl"))),
            Button(UkIcon("wand-sparkles", height=16, width=16), "Completar países automáticamente", cls=ButtonT.default,
                   hx_post="/personas/externos/completar",
                   title="Normaliza los países escritos y deduce los que faltan desde la institución"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P(f"{n_sin} persona(s) sin país.", cls="text-sm text-amber-700" if n_sin else "text-sm text-green-700"),
        fh.Form(Input(type="search", name="q", value=q, placeholder="Buscar por nombre o institución…",
                      cls="uk-input max-w-sm", aria_label="Buscar personas externas"),
                fh.Label(fh.Input(type="checkbox", name="todos", value="1", checked=not sin_pais, cls="uk-checkbox"),
                         Span("Mostrar también las que ya tienen país", cls="text-sm"), cls="flex items-center gap-2"),
                hx_get="/personas/externos/tabla", hx_target="#tabla-externos", hx_swap="outerHTML",
                hx_trigger="input delay:300ms, change, search", onsubmit="return false", cls="flex flex-wrap gap-3 mb-4"),
        fh.Datalist(*[fh.Option(value=x) for x in paises.nombres()], id="lista-paises"),
        Card(tabla_externos(q, sin_pais)),
        usuario=auth, seccion="investigadores")


@rt("/personas/externos/tabla")
def get(auth, q: str = "", todos: bool = False):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    return tabla_externos(q, not todos)


@rt("/personas/externos/completar")
def post(auth, sess):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    normalizados, deducidos = personas.completar_paises()
    auditar(auth["id"], "completar_paises", "persona_externa", None, f"{normalizados} normalizados, {deducidos} deducidos")
    add_toast(sess, f"Países: {deducidos} deducido(s) de la institución y {normalizados} normalizado(s).", "success")
    return HtmxResponseHeaders(refresh="true")


@rt("/personas/externos/{eid}")
def put(auth, eid: int, institucion: str = "", pais: str = ""):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    personas.actualizar_externo(eid, institucion, pais)
    auditar(auth["id"], "editar_externo", "persona_externa", eid, pais)
    e = next((x for x in personas.externos() if x["id"] == eid), None)
    return fila_externo(e) if e else ""
