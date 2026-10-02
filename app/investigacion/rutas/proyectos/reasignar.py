"""Reasignar al responsable de un proyecto (administración)."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Input, Option, P, Redirect, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Form, FormLabel, TextPresets

from app.investigacion import proyectos
from app.comun import usuarios
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.db import auditar

rt = APIRouter()


# --- Reasignar responsable (administración) --------------------------------------------------------------

def form_reasignar(p, errores=(), nuevo="", anterior="co_investigador"):
    actuales = {r["id"] for r in proyectos.responsables(p["id"])}
    candidatos = [u for u in usuarios.listar() if u["es_investigador"] and u["activo"] and u["id"] not in actuales]
    return modal(
        "Reasignar responsable",
        Form(mensaje_error(*errores),
             P("Úselo cuando el responsable deja el instituto o el proyecto cambia de manos. Los registros "
               "ya aprobados siguen en el proyecto.", cls=TextPresets.muted_sm),
             Div(FormLabel("Nuevo responsable", fr="nuevo"),
                 Select(Option("— Seleccione —", value=""),
                        *[Option(f"{u['apellidos']}, {u['nombres']}", value=str(u["id"]),
                                 selected=str(u["id"]) == nuevo) for u in candidatos],
                        id="nuevo", name="nuevo", cls="uk-select"), cls="space-y-2"),
             Div(FormLabel("El responsable actual"),
                 *[fh.Label(Input(type="radio", name="anterior", value=v, checked=v == anterior, cls="uk-radio"),
                            Span(t, cls="text-sm"), cls="flex items-center gap-2")
                   for v, t in (("co_investigador", "sigue en el proyecto como co-investigador(a)"),
                                ("baja", "deja el proyecto (se le da de baja con fecha de hoy)"))],
                 cls="space-y-2"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Reasignar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"/proyectos/{p['id']}/responsable", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt("/proyectos/{pid}/responsable")
def get(auth, pid: int):
    p = proyectos.obtener(pid)
    if not p or not proyectos.puede_reasignar(auth):
        return Response("No autorizado", status_code=403)
    return form_reasignar(p)


@rt("/proyectos/{pid}/responsable")
def post(auth, sess, pid: int, nuevo: str = "", anterior: str = "co_investigador"):
    p = proyectos.obtener(pid)
    if not p or not proyectos.puede_reasignar(auth):
        return Response("No autorizado", status_code=403)
    error = proyectos.reasignar_responsable(pid, int(nuevo), anterior) if nuevo.isdigit() \
        else "Seleccione al nuevo responsable."
    if error:
        return form_reasignar(p, [error], nuevo, anterior)
    auditar(auth["id"], "reasignar_responsable", "proyecto", pid, f"{nuevo} (anterior: {anterior})")
    add_toast(sess, "Responsable reasignado.", "success")
    return Redirect(f"/proyectos/{pid}?tab=participantes")
