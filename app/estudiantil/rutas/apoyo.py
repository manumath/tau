"""Casos de apoyo estudiantil para quien atiende (PLAN §67, etapa 8): el tutor(a) ve los de sus tutorados y la Dirección de Carrera,
todos. Solo hay casos que el estudiante pidió o que su tutor(a) o la Dirección abrieron avisándole."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import estudiantes, formato, permisos
from app.comun.componentes.layout import campo, pagina
from app.comun.componentes.registros import insignia
from app.estudiantil import apoyo, tutoria
from app.estudiantil.rutas.mi_apoyo import TONO

rt = APIRouter()
BASE = "/apoyo"


def _no():
    return Response("No autorizado", status_code=403)


def _atiende(auth) -> bool:
    return permisos.puede(auth, "gestionar_apoyo") or estudiantes.es_tutor(auth["id"])


@rt(BASE)
def get(auth, todos: str = ""):
    if not _atiende(auth):
        return _no()
    casos = apoyo.listar(auth, incluir_cerrados=todos == "1")
    return pagina(
        "Apoyo estudiantil", H2("Apoyo estudiantil"),
        P("Casos de apoyo de " + ("todos los estudiantes" if permisos.puede(auth, "gestionar_apoyo") else "sus tutorados")
          + ": los que el estudiante pidió y los que usted abrió avisándole. Cada caso vence a los seis meses si no se renueva. "
            "Para ofrecer apoyo a un tutorado, ábralo desde su ficha de tutoría.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        A("Ver también los cerrados" if todos != "1" else "Ocultar los cerrados", href=BASE + ("" if todos == "1" else "?todos=1"),
          cls="text-sm text-primary hover:underline"),
        Card(Ul(*[Li(Div(A(f"{c['apellidos']}, {c['nombres']}", href=f"{BASE}/{c['id']}", cls="font-medium hover:underline"),
                         insignia(apoyo.ESTADOS[c["estado_efectivo"]], TONO[c["estado_efectivo"]]),
                         insignia(apoyo.TEMAS[c["tema"]], "azul"), Span(apoyo.ORIGENES[c["origen"]], cls=TextPresets.muted_sm),
                         cls="flex flex-wrap items-center gap-2"),
                     P(f"Vence el {formato.fecha(c['vence_el'])}", cls=TextPresets.muted_sm), cls="py-3") for c in casos],
                cls="divide-y divide-border")) if casos else Card(P("No hay casos de apoyo.", cls="text-sm")), usuario=auth)


@rt(f"{BASE}/{{cid}}")
def get(auth, cid: int):
    c = apoyo.obtener(cid)
    if not c:
        return Response("No encontrado", status_code=404)
    if not apoyo.puede_atender(auth, c):
        return _no()
    msgs = apoyo.mensajes(cid)
    abierto = c["estado"] != "cerrado"
    return pagina(
        f"Apoyo: {c['nombres']} {c['apellidos']}", A(UkIcon("arrow-left", height=14, width=14), "Apoyo estudiantil", href=BASE,
                                                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"{c['nombres']} {c['apellidos']}"),
        Div(insignia(apoyo.ESTADOS[c["estado_efectivo"]], TONO[c["estado_efectivo"]]), insignia(apoyo.TEMAS[c["tema"]], "azul"),
            Span(f"{apoyo.ORIGENES[c['origen']]} ({c['por_nombres']} {c['por_apellidos']})", cls=TextPresets.muted_sm),
            Span(c["email"] or "", cls=TextPresets.muted_sm), cls="flex flex-wrap items-center gap-2 mb-4"),
        Card(P(c["motivo"], cls="text-sm whitespace-pre-line"),
             P(f"Vence el {formato.fecha(c['vence_el'])}." + (" Ya venció: renuévelo si sigue en seguimiento." if c["vencido"] else ""),
               cls=(TextPresets.muted_sm, "mt-2")),
             P("El estudiante ve todo lo que escriba aquí.", cls=TextPresets.muted_sm)),
        Card(H3("Conversación", cls="text-base font-semibold mb-1"),
             Ul(*[Li(Span(f"{m['nombres']} {m['apellidos']}" + (" (estudiante)" if m["del_estudiante"] else ""), cls="text-xs font-semibold"),
                     Span(f" · {formato.fecha_hora(m['creado_en'])}", cls=TextPresets.muted_sm),
                     P(m["texto"], cls="text-sm whitespace-pre-line"), cls="py-2") for m in msgs], cls="divide-y divide-border")
             if msgs else P("Todavía no hay mensajes.", cls=TextPresets.muted_sm),
             fh.Form(campo("Responder al estudiante", fh.Textarea("", name="texto", rows=3, maxlength="2000", cls="uk-textarea")),
                     Button("Enviar", type="submit", cls=(ButtonT.primary, ButtonT.sm)), method="post",
                     action=f"{BASE}/{cid}/mensaje", cls="space-y-2 mt-3") if abierto else "", cls="mt-4"),
        Card(H3("Seguimiento", cls="text-base font-semibold mb-2"),
             fh.Form(campo("Derivación", Select(*[Option(t, value=k, selected=k == c["derivacion"])
                                                  for k, t in apoyo.DERIVACIONES.items()], name="derivacion", cls="uk-select")),
                     Div(Button("Pasar a «en seguimiento»", type="submit", formaction=f"{BASE}/{cid}/estado/en_seguimiento",
                                cls=ButtonT.default),
                         Button("Renovar seis meses", type="submit", formaction=f"{BASE}/{cid}/renovar", cls=ButtonT.default),
                         Button("Cerrar el caso", type="submit", formaction=f"{BASE}/{cid}/estado/cerrado", cls=ButtonT.primary),
                         cls="flex flex-wrap gap-2 mt-2"), method="post", cls="space-y-2") if abierto
             else P("Cerrado.", cls="text-sm"), cls="mt-4"), usuario=auth)


def _atender(auth, cid):
    c = apoyo.obtener(cid)
    return c, (None if c and apoyo.puede_atender(auth, c) else _no())


@rt(f"{BASE}/{{cid}}/mensaje")
def post(auth, sess, cid: int, texto: str = ""):
    c, error = _atender(auth, cid)
    if error:
        return error
    errores = apoyo.responder(cid, texto, auth, False)
    add_toast(sess, errores[0] if errores else "Respuesta enviada: se avisó al estudiante.", "error" if errores else "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/estado/{{estado}}")
def post(auth, sess, cid: int, estado: str, derivacion: str = ""):
    c, error = _atender(auth, cid)
    if error:
        return error
    errores = apoyo.cambiar_estado(cid, estado, auth, derivacion)
    add_toast(sess, errores[0] if errores else "Guardado.", "error" if errores else "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/renovar")
def post(auth, sess, cid: int):
    c, error = _atender(auth, cid)
    if error:
        return error
    errores = apoyo.renovar(cid, auth)
    add_toast(sess, errores[0] if errores else "Renovado por seis meses.", "error" if errores else "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/ofrecer/{{externo_id}}")
def post(auth, sess, externo_id: int, tema: str = "", motivo: str = ""):
    """El tutor(a) del estudiante o la Dirección de Carrera abren un caso avisándole."""
    es_tutor = tutoria.es_tutor_de(auth["id"], externo_id)
    if not (es_tutor or permisos.puede(auth, "gestionar_apoyo")):
        return _no()
    cid, errores = apoyo.abrir(externo_id, tema, motivo, auth, "tutor" if es_tutor else "direccion")
    add_toast(sess, errores[0] if errores else "Caso abierto: se avisó al estudiante.", "error" if errores else "success")
    return Redirect(f"{BASE}/{cid}" if cid else f"/tutoria/{externo_id}")
