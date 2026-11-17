"""«Apoyo» del estudiante (PLAN §67, etapa 8): lo que TAU observa de él (solo él lo ve), el pedido de apoyo y la conversación de su
caso con su tutor(a) y la Dirección de Carrera."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import formato
from app.comun.componentes.layout import campo, pagina
from app.comun.componentes.registros import insignia
from app.estudiantil import apoyo
from app.estudiantil.rutas.estudiante import _requiere

rt = APIRouter()
BASE = "/estudiante/apoyo"
TONO = {"abierto": "ambar", "en_seguimiento": "azul", "cerrado": "gris", "vencido": "gris"}


def _caso(c):
    msgs = apoyo.mensajes(c["id"])
    activo = c["estado"] != "cerrado"
    return Card(
        Div(insignia(apoyo.ESTADOS[c["estado_efectivo"]], TONO[c["estado_efectivo"]]), insignia(apoyo.TEMAS[c["tema"]], "azul"),
            Span(apoyo.ORIGENES[c["origen"]], cls=TextPresets.muted_sm), cls="flex flex-wrap items-center gap-2"),
        P(c["motivo"], cls="text-sm whitespace-pre-line mt-2"),
        P(f"Derivado a: {apoyo.DERIVACIONES[c['derivacion']]}.", cls="text-sm") if c["derivacion"] != "ninguna" else "",
        P(f"Vence el {formato.fecha(c['vence_el'])} si nadie lo renueva." if not c["vencido"] else
          "Este caso venció: si todavía necesita apoyo, abra uno nuevo.", cls=TextPresets.muted_sm) if activo else "",
        Ul(*[Li(Span(f"{m['nombres']} {m['apellidos']}", cls="text-xs font-semibold"),
                Span(f" · {formato.fecha_hora(m['creado_en'])}", cls=TextPresets.muted_sm), P(m["texto"], cls="text-sm whitespace-pre-line"),
                cls="py-2") for m in msgs], cls="divide-y divide-border mt-2") if msgs else "",
        fh.Form(campo("Escribir un mensaje", fh.Textarea("", name="texto", rows=3, maxlength="2000", cls="uk-textarea")),
                Div(Button("Enviar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                    Button("Ya no lo necesito: cerrar", type="submit", formaction=f"{BASE}/{c['id']}/cerrar",
                           formnovalidate=True, cls=(ButtonT.ghost, ButtonT.sm)), cls="flex gap-2 mt-2"),
                method="post", action=f"{BASE}/{c['id']}/mensaje") if activo and not c["vencido"] else "", cls="mb-4")


@rt(BASE)
def get(auth):
    externo, error = _requiere(auth)
    if error:
        return error
    casos = apoyo.casos_de(externo)
    abierto = any(c["estado"] != "cerrado" and not c["vencido"] for c in casos)
    sen = apoyo.senales(externo)
    return pagina(
        "Apoyo", H2("Apoyo"),
        P("Si necesita ayuda académica, económica, de salud o de otro tipo, pídala aquí: su tutor(a) y la Dirección de Carrera lo ven "
          "y le responden por este mismo lugar.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Div(Card(H3("Lo que TAU observa de usted", cls="text-base font-semibold mb-1"),
                 P("Solo usted ve esto. No se guarda como una etiqueta ni lo ve nadie más: se calcula con los datos que la Carrera "
                   "cargó y con su actividad en el sistema.", cls=(TextPresets.muted_sm, "mb-2")),
                 Ul(*[Li(Div(UkIcon("info", height=14, width=14, cls="shrink-0 mt-0.5 text-primary"), Span(s["texto"], cls="text-sm"),
                             cls="flex gap-2 items-start"), cls="py-1") for s in sen]) if sen else
                 P("No hay nada que destacar.", cls="text-sm")),
            Card(H3("Pedir apoyo", cls="text-base font-semibold mb-2"),
                 P("Ya tiene un caso abierto (abajo).", cls="text-sm") if abierto else fh.Form(
                     campo("¿Sobre qué?", Select(*[Option(t, value=k) for k, t in apoyo.TEMAS.items()], name="tema", cls="uk-select")),
                     campo("Cuéntenos qué necesita", fh.Textarea("", name="motivo", rows=4, minlength="10", maxlength="2000",
                                                                  required=True, cls="uk-textarea")),
                     P("Lo verán su tutor(a) y la Dirección de Carrera, y nadie más. Lo que cuente aquí no se usa en informes.",
                       cls=TextPresets.muted_sm),
                     Button("Pedir apoyo", type="submit", cls=ButtonT.primary), method="post", action=BASE, cls="space-y-3")),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4 items-start"),
        *[_caso(c) for c in casos], usuario=auth)


@rt(BASE)
def post(auth, sess, tema: str = "", motivo: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    cid, errores = apoyo.abrir(externo, tema, motivo, auth, "estudiante")
    add_toast(sess, errores[0] if errores else "Se avisó a su tutor(a) y a la Dirección de Carrera.", "error" if errores else "success")
    return Redirect(BASE)


def _propio(externo, cid):
    c = apoyo.obtener(cid)
    return c if c and c["externo_id"] == externo else None


@rt(f"{BASE}/{{cid}}/mensaje")
def post(auth, sess, cid: int, texto: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    if not _propio(externo, cid):
        return Response("No encontrado", status_code=404)
    errores = apoyo.responder(cid, texto, auth, True)
    add_toast(sess, errores[0] if errores else "Mensaje enviado.", "error" if errores else "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{cid}}/cerrar")
def post(auth, sess, cid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = apoyo.cerrar_por_el_estudiante(cid, externo)
    if errores:
        return Response("No encontrado", status_code=404)
    add_toast(sess, "Caso cerrado.", "info")
    return Redirect(BASE)
