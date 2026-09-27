"""Pestaña «Pendientes»: propuestas de vinculación por aprobar o rechazar."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, Option, P, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Card, FormLabel, LabelTextArea, TextPresets, UkIcon

from app.investigacion import actividades, filiacion, productos, proyectos
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.investigacion.rutas.proyectos.base import EVENTO_PENDIENTES, ID_TAB, _proyecto_o_error, contador_pestana

rt = APIRouter()


# --- Pestaña: pendientes -----------------------------------------------------------------------------------------

OPCIONES_AGRADECE = (("", "Agradecimiento sin declarar"), ("1", "Agradece al proyecto"), ("0", "No agradece al proyecto"))


def _selector_agradece(valor, **kw):
    actual = "" if valor is None else str(valor)
    return Div(FormLabel("¿La publicación agradece al proyecto?") if not kw else "",
               Select(*[Option(t, value=v, selected=v == actual) for v, t in OPCIONES_AGRADECE],
                      name="agradece", aria_label="¿La publicación agradece al proyecto?",
                      cls="uk-select h-8 w-56 text-sm" + (" border-amber-400 text-amber-700" if actual == "" else ""),
                      **kw),
               cls="space-y-1")


def _requisitos(x, v):
    """Lo que exigen los fondos: filiación IIMAT/UMSA y agradecimiento al proyecto."""
    fil, agr = filiacion.estado_producto(x), v.get("agradece")
    return [insignia({1: "Filiación IIMAT/UMSA", 0: "Sin filiación del instituto", None: "Filiación sin declarar"}[fil],
                     {1: "verde", 0: "rojo", None: "ambar"}[fil]),
            insignia({1: "Agradece al proyecto", 0: "No agradece al proyecto", None: "Agradecimiento sin declarar"}[agr],
                     {1: "verde", 0: "rojo", None: "ambar"}[agr])]


def _tarjeta_pendiente(p, tipo, v, vigentes):
    pid, rid = p["id"], v["registro_id"]
    if tipo == "producto":
        x = productos.obtener(rid)
        titulo = A(x["titulo"], href=f"/productos/{rid}", target="_blank", cls="font-medium hover:underline")
        detalle = P(productos.cita(x), cls="text-sm")
        etiqueta = insignia(x["tipo"])
    else:
        x = actividades.obtener(rid)
        titulo = A(x["titulo"], href=f"/actividades/{rid}", target="_blank", cls="font-medium hover:underline")
        detalle = P(f"{actividades.fechas_texto(x)} · "
                    + ", ".join(y for y in (x["institucion"], x["lugar"], x["pais"]) if y), cls="text-sm")
        etiqueta = insignia(x["tipo"])
    caja_id = f"pendiente-{tipo}-{rid}"
    responsable = Div(FormLabel("Responsable de la actividad (opcional)", fr=f"resp-{rid}"),
                      Select(Option("— Sin responsable —", value=""),
                             *[Option(f"{y['nombres']} {y['apellidos']}", value=str(y["participante_id"]),
                                      selected=y["id"] == v["propuesto_por"] and y["interno"])
                               for y in vigentes],
                             id=f"resp-{rid}", name="responsable", cls="uk-select h-9 text-sm"),
                      cls="space-y-1 max-w-sm") if tipo == "actividad" else _selector_agradece(v.get("agradece"))
    fuera = insignia("Fuera del periodo del proyecto", "ambar", icono="triangle-alert") \
        if proyectos.fuera_de_periodo(p, tipo, x) else ""
    return Card(
        Div(etiqueta, fuera, Span(f"Propuesto por {v['propuesto_por_nombre']}", cls=TextPresets.muted_sm),
            cls="flex flex-wrap items-center gap-2"),
        Div(titulo, detalle, cls="space-y-1 my-2"),
        responsable,
        Div(Button(UkIcon("check", height=14, width=14), "Aprobar", cls=(ButtonT.primary, ButtonT.sm),
                   hx_post=f"/proyectos/{pid}/pendientes/{tipo}/{rid}/aprobar", hx_include=f"#{caja_id}",
                   hx_target=f"#{ID_TAB}"),
            Button(UkIcon("x", height=14, width=14), "Rechazar…", cls=(ButtonT.ghost, ButtonT.sm),
                   hx_get=f"/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar", hx_target=f"#motivo-{tipo}-{rid}"),
            cls="flex gap-2 mt-3"),
        Div(id=f"motivo-{tipo}-{rid}"),
        id=caja_id)


def tab_pendientes(p, auth):
    pid = p["id"]
    vigentes = proyectos.participantes(pid, solo_vigentes=True)
    tarjetas = [_tarjeta_pendiente(p, "actividad", v, vigentes)
                for v in proyectos.registros(pid, "actividad", "pendiente")]
    tarjetas += [_tarjeta_pendiente(p, "producto", v, vigentes)
                 for v in proyectos.registros(pid, "producto", "pendiente")]
    return Div(
        P("Actividades y productos que los participantes proponen para el proyecto. Al aprobarlos pasan "
          "a formar parte de él; si los rechaza, indique el motivo: quien los propuso lo verá.",
          cls=(TextPresets.muted_sm, "mb-4")),
        Div(*tarjetas, cls="space-y-4") if tarjetas
        else Card(P(UkIcon("inbox", height=16, width=16, cls="inline mr-2"), "No hay propuestas pendientes.",
                    cls=(TextPresets.muted_sm, "text-center py-6"))))


def _tras_revision(p, auth):
    """Bandeja actualizada + contador de la pestaña (fuera de banda) + evento para la navegación."""
    return (tab_pendientes(p, auth), contador_pestana(p["id"], oob=True),
            HtmxResponseHeaders(trigger=EVENTO_PENDIENTES))


@rt("/proyectos/{pid}/pendientes/{tipo}/{rid}/aprobar")
def post(auth, sess, pid: int, tipo: str, rid: int, responsable: str = "", agradece: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error or tipo not in proyectos.TABLAS:
        return error or Response(status_code=404)
    error = proyectos.aprobar(tipo, rid, pid, auth["id"], int(responsable) if responsable.isdigit() else None)
    if error:
        add_toast(sess, error, "error")
    else:
        if tipo == "producto":
            proyectos.marcar_agradece(rid, pid, filiacion.normalizar(agradece))
        auditar(auth["id"], "aprobar", tipo, rid, f"proyecto {pid}")
        add_toast(sess, "Aprobado: ya forma parte del proyecto.", "success")
    return _tras_revision(p, auth)


@rt("/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar")
def get(auth, pid: int, tipo: str, rid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    return fh.Form(
        LabelTextArea("Motivo del rechazo", id=f"comentario-{tipo}-{rid}", name="comentario", rows=2,
                      required=True, placeholder="Por ejemplo: el artículo no menciona el financiamiento del proyecto."),
        Div(Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                   onclick=f"document.getElementById('motivo-{tipo}-{rid}').innerHTML=''"),
            Button("Rechazar", type="submit", cls=(ButtonT.destructive, ButtonT.sm)),
            cls="flex justify-end gap-2"),
        hx_post=f"/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar", hx_target=f"#{ID_TAB}",
        cls="space-y-2 mt-3 rounded-md border border-border p-3")


@rt("/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar")
def post(auth, sess, pid: int, tipo: str, rid: int, comentario: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error or tipo not in proyectos.TABLAS:
        return error or Response(status_code=404)
    error = proyectos.rechazar(tipo, rid, pid, auth["id"], comentario)
    if error:
        add_toast(sess, error, "error")
    else:
        auditar(auth["id"], "rechazar", tipo, rid, f"proyecto {pid}: {comentario.strip()}")
        add_toast(sess, "Propuesta rechazada. Quien la propuso verá el motivo.", "success")
    return _tras_revision(p, auth)
