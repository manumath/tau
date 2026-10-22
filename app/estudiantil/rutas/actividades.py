"""Verificación de la actividad estudiantil declarada (PLAN §49): la Dirección de Carrera y la Coordinación
académica ven lo que los estudiantes declararon, miran la evidencia y lo verifican o piden correcciones."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, P, Response, Span, Thead, Tr
from monsterui.all import H2, Button, ButtonT, Card, Form, FormLabel, Table, Tbody, Td, TextPresets, Th, UkIcon

from app.academico.componentes import pestanas
from app.comun import permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, cerrar_modal, mensaje_error, modal, pagina
from app.estudiantil import actividad
from app.estudiantil.rutas.estudiante import respuesta_evidencia
from app.investigacion import adjuntos

rt = APIRouter()
BASE = "/docencia/cohortes/actividades"
ID_LISTA = "actividades-por-verificar"


def _puede(auth) -> bool:
    return permisos.puede(auth, "verificar_actividad", vinculos.carrera())


def _lista():
    filas = []
    for a in actividad.pendientes():
        evidencias = [A(UkIcon("paperclip", height=12, width=12), e["nombre"], href=f"{BASE}/evidencia/{e['id']}",
                        target="_blank", cls="inline-flex items-center gap-1 text-sm text-primary hover:underline")
                      for e in a["evidencias"]]
        filas.append(Tr(
            Td(f"{a['apellidos']}, {a['nombres']}", cls="font-medium"),
            Td(Div(Span(a["titulo"], cls="font-medium"), Div(f"{actividad.TIPOS[a['tipo']]} · {a['fecha_inicio']}"
                   + (f" a {a['fecha_fin']}" if a["fecha_fin"] else "") + (f" · {a['institucion']}" if a["institucion"] else ""),
                                                                 cls=TextPresets.muted_sm),
                   P(a["descripcion"], cls="text-sm") if a["descripcion"] else "")),
            Td(Div(*evidencias, cls="flex flex-col gap-1") if evidencias else Span("Sin evidencia", cls=TextPresets.muted_sm)),
            Td(Div(Button("Verificar", type="button", cls=(ButtonT.primary, ButtonT.sm), hx_post=f"{BASE}/{a['id']}/verificar",
                          hx_target=f"#{ID_LISTA}", hx_swap="outerHTML"),
                   Button("Observar", type="button", cls=(ButtonT.default, ButtonT.sm), hx_get=f"{BASE}/{a['id']}/observar",
                          hx_target=f"#{ID_MODAL}"), cls="flex gap-2"))))
    return Div(Table(Thead(Tr(Th("Estudiante"), Th("Actividad"), Th("Evidencia"), Th(""))),
                     Tbody(*filas) if filas else Tbody(Tr(Td("No hay actividades por verificar.", colspan=4,
                                                             cls=(TextPresets.muted_sm, "text-center py-6")))),
                     cls="uk-table-divider uk-table-middle"), id=ID_LISTA, cls="overflow-x-auto")


@rt(BASE)
def get(auth):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    return pagina(
        "Actividad estudiantil por verificar",
        pestanas("cohortes", auth),
        A(UkIcon("arrow-left", height=14, width=14), "Cohortes estudiantiles", href="/docencia/cohortes",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Actividad estudiantil por verificar"),
        P("Lo que los estudiantes declararon (ayudantías, olimpiadas, pasantías, becas…). Verifíquelo si la evidencia lo "
          "respalda; si falta algo, indíquelo con «Observar» y el estudiante recibirá un aviso.",
          cls=(TextPresets.muted_sm, "max-w-3xl mb-6")),
        Card(_lista()), usuario=auth, seccion="docencia")


@rt(f"{BASE}/{{aid}}/verificar")
def post(auth, aid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    actividad.verificar(aid, auth["id"])
    return _lista()


def _form_observar(aid, errores=()):
    return modal("Pedir correcciones",
                 Form(mensaje_error(*errores),
                      Div(FormLabel("¿Qué debe corregir o aclarar el estudiante?"),
                          fh.Textarea(name="observacion", rows="4", maxlength="1000", cls="uk-textarea", required=True),
                          cls="space-y-1"),
                      Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                          Button("Enviar observación", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
                      hx_post=f"{BASE}/{aid}/observar", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/{{aid}}/observar")
def get(auth, aid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    return _form_observar(aid)


@rt(f"{BASE}/{{aid}}/observar")
def post(auth, aid: int, observacion: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    errores = actividad.observar(aid, auth["id"], observacion)
    return _form_observar(aid, errores) if errores else (_lista(), cerrar_modal())


@rt(f"{BASE}/evidencia/{{adj_id}}")
def get(auth, adj_id: int):
    adj = adjuntos.obtener(adj_id)
    if not _puede(auth) or not adj or adj["entidad"] != actividad.ENTIDAD:
        return Response("No encontrada", status_code=404)
    return respuesta_evidencia(adj)
