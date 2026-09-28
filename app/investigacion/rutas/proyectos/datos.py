"""Alta de proyectos individuales y edición de sus datos."""
from fasthtml.common import APIRouter, Div, H3, Option, P, Redirect, Response, Select
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Card, Form, FormLabel, LabelInput, LabelTextArea, TextPresets

from app.investigacion import proyectos
from app.comun import config
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal
from app.comun.db import auditar
from app.investigacion.rutas.proyectos.base import ID_TAB, _proyecto_o_error

rt = APIRouter()


# --- Alta y edición de datos -------------------------------------------------------------------------

def _selector_ambito(d):
    return Div(FormLabel("Ámbito", fr="ambito"),
               Select(Option("— Sin indicar —", value=""),
                      *[Option(t, value=v, selected=v == d.get("ambito")) for v, t in proyectos.AMBITOS.items()],
                      id="ambito", name="ambito", cls="uk-select"),
               P("Internacional: con instituciones o financiamiento de otros países.", cls=TextPresets.muted_sm),
               cls="space-y-2")


def form_datos_institucional(d, errores, pid):
    """En un proyecto institucional, el nombre, la descripción, los objetivos y el periodo vienen de
    la propuesta aceptada; aquí solo se editan datos administrativos."""
    def campo(etiqueta, nombre, **kw):
        return LabelInput(etiqueta, id=nombre, value="" if d.get(nombre) is None else d.get(nombre), **kw)
    return Form(
        P("Nombre, descripción, objetivos y periodo vienen de la propuesta aceptada: se cambian en la "
          "propuesta de continuidad.", cls=TextPresets.muted_sm),
        mensaje_error(*errores),
        campo("Código", "codigo", placeholder="Código interno o de la agencia"),
        Div(Div(campo("Fuente de financiamiento", "fuente_financiamiento"), cls="sm:col-span-2"),
            campo(f"Monto ({d.get('moneda') or config.MONEDA})", "monto", inputmode="numeric"),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
        _selector_ambito(d),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, hx_get=f"/proyectos/{pid}/tab/resumen",
                   hx_target=f"#{ID_TAB}"),
            Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_put=f"/proyectos/{pid}/datos", hx_target=f"#{ID_TAB}", cls="space-y-4")


def form_datos(d, errores=(), pid=None):
    def campo(etiqueta, nombre, **kw):
        return LabelInput(etiqueta, id=nombre, value="" if d.get(nombre) is None else d.get(nombre), **kw)

    if pid and d.get("tipo") == "institucional":
        return form_datos_institucional(d, errores, pid)
    return Form(
        P("Usted quedará como responsable: podrá agregar participantes y aprobar sus propuestas. "
          "Los proyectos institucionales no se crean aquí: se proponen en la convocatoria de septiembre.",
          cls=TextPresets.muted_sm) if not pid else "",
        mensaje_error(*errores),
        Div(campo("Nombre del proyecto", "nombre", required=True), cls="sm:col-span-2"),
        Div(Div(campo("Código", "codigo", placeholder="IDH-IIMAT-2026-01"), cls="sm:col-span-2"),
            Div(FormLabel("Estado", fr="estado"),
                Select(*[Option(t, value=v, selected=v == d.get("estado")) for v, t in proyectos.ESTADOS.items()],
                       id="estado", name="estado", cls="uk-select"), cls="space-y-2"),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
        Div(campo("Inicio", "fecha_inicio", type="date"), campo("Término", "fecha_fin", type="date"),
            cls="grid grid-cols-2 gap-4"),
        Div(Div(campo("Fuente de financiamiento", "fuente_financiamiento"), cls="sm:col-span-2"),
            campo(f"Monto ({d.get('moneda') or config.MONEDA})", "monto", inputmode="numeric"),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
        _selector_ambito(d),
        LabelTextArea("Descripción", id="descripcion", value=d.get("descripcion") or "", rows=3),
        LabelTextArea("Objetivo general", id="objetivo_general", value=d.get("objetivo_general") or "",
                      rows=2),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost,
                   **({"hx_get": f"/proyectos/{pid}/tab/resumen", "hx_target": f"#{ID_TAB}"} if pid
                      else {"onclick": JS_CERRAR})),
            Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        **({"hx_put": f"/proyectos/{pid}/datos", "hx_target": f"#{ID_TAB}"} if pid
           else {"hx_post": "/proyectos", "hx_target": f"#{ID_MODAL}"}),
        cls="space-y-4")


def _datos(nombre, codigo, estado, fecha_inicio, fecha_fin, fuente_financiamiento, monto, descripcion,
           objetivo_general, ambito=""):
    d = dict(nombre=nombre, codigo=codigo, estado=estado, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
             fuente_financiamiento=fuente_financiamiento, monto=monto, descripcion=descripcion,
             objetivo_general=objetivo_general, ambito=ambito if ambito in proyectos.AMBITOS else "")
    return {k: (v.strip() or None) if isinstance(v, str) else v for k, v in d.items()}


@rt("/proyectos/nuevo")
def get(auth):
    if not proyectos.puede_crear(auth):
        return Response("No autorizado", status_code=403)
    return modal("Nuevo proyecto individual", form_datos({"estado": "vigente"}), ancho="max-w-2xl")


@rt("/proyectos")
def post(auth, sess, nombre: str = "", codigo: str = "", estado: str = "", fecha_inicio: str = "",
         fecha_fin: str = "", fuente_financiamiento: str = "", monto: str = "", descripcion: str = "",
         objetivo_general: str = "", ambito: str = ""):
    if not proyectos.puede_crear(auth):
        return Response("No autorizado", status_code=403)
    d = _datos(nombre, codigo, estado, fecha_inicio, fecha_fin, fuente_financiamiento, monto,
               descripcion, objetivo_general, ambito)
    errores = proyectos.validar(d)
    if errores:
        return modal("Nuevo proyecto individual", form_datos(d, errores), ancho="max-w-2xl")
    pid = proyectos.crear(d, auth["id"], auth["id"], tipo="individual")
    auditar(auth["id"], "crear_proyecto", "proyecto", pid, d["nombre"])
    add_toast(sess, "Proyecto creado.", "success")
    return Redirect(f"/proyectos/{pid}")


@rt("/proyectos/{pid}")
def delete(auth, sess, pid: int):
    p = proyectos.obtener(pid)
    if not p:
        return Response("No encontrado", status_code=404)
    if not proyectos.puede_eliminar(p, auth):
        return Response("Solo el responsable puede eliminar un proyecto individual.", status_code=403)
    proyectos.eliminar(pid)
    auditar(auth["id"], "eliminar_proyecto", "proyecto", pid, p["nombre"])
    add_toast(sess, f"Proyecto «{p['nombre']}» eliminado.", "success")
    return Redirect("/proyectos")


@rt("/proyectos/{pid}/datos/editar")
def get(auth, pid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    return error or Card(H3("Editar datos del proyecto", cls="text-base font-semibold mb-4"),
                         form_datos(p, pid=pid))


@rt("/proyectos/{pid}/datos")
def put(auth, sess, pid: int, nombre: str = "", codigo: str = "", estado: str = "",
        fecha_inicio: str = "", fecha_fin: str = "", fuente_financiamiento: str = "", monto: str = "",
        descripcion: str = "", objetivo_general: str = "", ambito: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    d = _datos(nombre, codigo, estado, fecha_inicio, fecha_fin, fuente_financiamiento, monto,
               descripcion, objetivo_general, ambito)
    if p["tipo"] == "institucional":
        # Solo datos administrativos; el resto lo fija la propuesta aceptada.
        d = {**{k: p[k] for k in ("nombre", "estado", "fecha_inicio", "fecha_fin", "descripcion",
                                  "objetivo_general")},
             **{k: d[k] for k in ("codigo", "fuente_financiamiento", "monto", "ambito")}}
    errores = proyectos.validar({**d, "id": pid})
    if errores:
        return Card(H3("Editar datos del proyecto", cls="text-base font-semibold mb-4"),
                    form_datos({**p, **d}, errores, pid))
    proyectos.actualizar(pid, d)
    auditar(auth["id"], "editar_proyecto", "proyecto", pid)
    add_toast(sess, "Datos del proyecto guardados.", "success")
    # La cabecera muestra nombre y estado: se recarga la página completa.
    return Redirect(f"/proyectos/{pid}?tab=resumen")
