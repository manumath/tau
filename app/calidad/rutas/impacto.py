"""Impacto de los proyectos de interacción social (PLAN §57, etapa 8): lo registran las direcciones de Carrera y del
Instituto y el responsable de cada proyecto; lo ven quienes ven el marco de calidad."""
from fasthtml.common import A, APIRouter, Div, P, Redirect, Response, Span, Table, Tbody, Td, Th, Thead, Tr
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Form, LabelCheckboxX, LabelInput, LabelTextArea, TextPresets, UkIcon

from app.calidad import evidencias, impacto, marco
from app.calidad.rutas.mejora import _botones_modal, _select
from app.comun import unidades
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.investigacion import proyectos

rt = APIRouter()
BASE = "/calidad/impacto"


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _registra(auth, m, pid):
    return marco.puede(auth, "registrar_impacto_proyectos", m) or impacto.es_responsable(auth["id"], pid)


@rt(BASE)
def get(auth):
    m = _marco()
    ve = marco.puede(auth, "ver_marco_calidad", m)
    if not ve and not impacto.tiene_proyectos(auth["id"]):
        return Response("No autorizado", status_code=403)
    lista = [p for p in impacto.proyectos() if ve or impacto.es_responsable(auth["id"], p["id"])]
    return pagina(
        "Impacto social",
        H2("Impacto de los proyectos de interacción social"),
        P("A quiénes llegó cada proyecto institucional de interacción social y qué cambió. Un impacto «comprobado» necesita "
          "su evidencia (informe de evaluación, encuesta a beneficiarios, registro de la contraparte). Alimenta el indicador "
          "«Proyectos con impacto social comprobado». Lo registran las direcciones y el responsable del proyecto.",
          cls="text-sm max-w-3xl my-4"),
        Div(Table(Thead(Tr(Th("Proyecto"), Th("Estado", cls="w-24"), Th("Beneficiarios", cls="w-28 text-right"),
                           Th("Impacto", cls="w-40"), Th("", cls="w-24"))),
                  Tbody(*[Tr(Td(A(p["nombre"], href=f"/proyectos/{p['id']}", cls="font-medium hover:underline"),
                                Div(p["impacto"] or "", cls=(TextPresets.muted_sm, "line-clamp-2"))),
                             Td(proyectos.ESTADOS[p["estado"]]),
                             Td(str(p["beneficiarios"]) if p["beneficiarios"] is not None else "—", cls="text-right"),
                             Td(insignia("Comprobado", "verde", icono="check") if p["comprobado"] else
                                insignia("Registrado", "azul") if p["registrado_en"] else insignia("Sin registrar", "gris")),
                             Td(Button(UkIcon("pencil", height=12, width=12), "Registrar", cls=(ButtonT.ghost, ButtonT.xs),
                                       hx_get=f"{BASE}/{p['id']}", hx_target=f"#{ID_MODAL}")
                                if _registra(auth, m, p["id"]) else ""))
                          for p in lista]),
                  cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[44rem]"), cls="overflow-x-auto")
        if lista else P(Span("No hay proyectos institucionales de interacción social."), cls=TextPresets.muted_sm),
        usuario=auth)


def _form(m, p, d, errores=()):
    def v(k):
        return d.get(k) if d.get(k) is not None else ""
    evs = [(e["id"], e["titulo"]) for e in evidencias.listar(m["id"])]
    return modal(
        "Impacto del proyecto",
        Form(mensaje_error(*errores), P(p["nombre"], cls="text-sm font-medium"),
             LabelInput("Beneficiarios (número de personas, opcional)", id="beneficiarios", type="number", min=0,
                        value=v("beneficiarios")),
             LabelTextArea("A quiénes llegó y qué cambió", id="descripcion", value=v("descripcion") or v("impacto"), rows=4),
             _select("Evidencia del impacto (del repositorio)", "evidencia_id", evs, v("evidencia_id"), "—"),
             LabelCheckboxX("Impacto comprobado (con evidencia)", id="comprobado", checked=bool(d.get("comprobado"))),
             _botones_modal(), hx_post=f"{BASE}/{p['id']}", hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-2xl")


@rt(f"{BASE}/{{pid}}")
def get(auth, pid: int):
    m, p = _marco(), impacto.proyecto(pid)
    if p is None:
        return Response("No encontrado", status_code=404)
    return _form(m, p, p) if _registra(auth, m, pid) else Response("No autorizado", status_code=403)


@rt(f"{BASE}/{{pid}}")
def post(auth, sess, pid: int, beneficiarios: str = "", descripcion: str = "", evidencia_id: str = "",
         comprobado: str = ""):
    m, p = _marco(), impacto.proyecto(pid)
    if p is None:
        return Response("No encontrado", status_code=404)
    if not _registra(auth, m, pid):
        return Response("No autorizado", status_code=403)
    x, errores = impacto.validar({"beneficiarios": beneficiarios, "descripcion": descripcion, "evidencia_id": evidencia_id,
                                  "comprobado": comprobado}, {e["id"] for e in evidencias.listar(m["id"])})
    if errores:
        return _form(m, p, x, errores)
    impacto.guardar(pid, x, auth["id"])
    auditar(auth["id"], "impacto_proyecto", "proyecto", pid, "comprobado" if x["comprobado"] else "registrado")
    add_toast(sess, "Impacto registrado.", "success")
    return Redirect(BASE)
