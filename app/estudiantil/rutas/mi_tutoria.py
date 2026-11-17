"""«Mi tutoría» del estudiante (PLAN §67, etapa 3): quién es su tutor(a), cuándo se reunieron (solo las fechas: lo que se
habló es confidencial) y el pedido de una reunión. Solo ve lo suyo: la ficha sale de su cuenta."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets

from app.comun import estudiantes, formato
from app.comun.componentes.layout import campo, mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.estudiantil import tutoria
from app.estudiantil.rutas.estudiante import _requiere

rt = APIRouter()
BASE = "/estudiante/tutoria"
TONOS = {"pendiente": "ambar", "programada": "azul", "atendida": "verde", "cancelada": "gris"}


def _formulario(errores=(), v=None):
    v = v or {}
    return fh.Form(
        mensaje_error(*errores),
        campo("¿De qué quiere hablar?", Select(*[Option(t, value=k, selected=v.get("tema") == k) for k, t in tutoria.TEMAS.items()],
                                              name="tema", cls="uk-select")),
        campo("Mensaje para su tutor(a) (opcional)",
              fh.Textarea(v.get("mensaje", ""), name="mensaje", rows=3, maxlength="1000", cls="uk-textarea")),
        P("Su tutor(a) recibe un aviso y le responde con la fecha. Lo que hablen en la reunión es confidencial: usted y su "
          "tutor(a) lo ven; no se usa en informes.", cls=TextPresets.muted_sm),
        Button("Pedir una reunión", type="submit", cls=ButtonT.primary), method="post", action=f"{BASE}/solicitud",
        cls="space-y-3")


def _solicitud(s):
    return Li(Div(Span(tutoria.TEMAS[s["tema"]], cls="font-medium text-sm"),
                  insignia(tutoria.ESTADOS_SOLICITUD[s["estado"]], TONOS[s["estado"]]),
                  Span(f"pedida el {formato.fecha_hora(s['creada_en']).split(',')[0]}", cls=TextPresets.muted_sm),
                  cls="flex flex-wrap items-center gap-2"),
              P(s["mensaje"], cls="text-sm") if s["mensaje"] else "",
              P(f"Reunión: {formato.momento(s['fecha_reunion'])}." + (f" {s['respuesta']}" if s["respuesta"] else ""),
                cls="text-sm font-medium") if s["fecha_reunion"] and s["estado"] in ("programada", "atendida") else "",
              fh.Form(Button("Cancelar la solicitud", type="submit", cls=(ButtonT.ghost, ButtonT.sm)), method="post",
                      action=f"{BASE}/solicitud/{s['id']}/cancelar") if s["estado"] in tutoria.ABIERTAS else "",
              cls="py-3 space-y-1")


@rt(BASE)
def get(auth, errores: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    tutor = estudiantes.tutor_de(externo)
    abiertas = [s for s in tutoria.solicitudes_de(externo) if s["estado"] in tutoria.ABIERTAS]
    reuniones = tutoria.fechas_de_reuniones(externo)
    return pagina(
        "Mi tutoría", H2("Mi tutoría"),
        P("Su tutor(a) lo orienta durante la carrera. Aquí ve quién es y cuándo se reunieron, y puede pedirle una reunión.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Div(Card(H3("Mi tutor(a)", cls="text-base font-semibold mb-1"),
                 Div(Span(f"{tutor['nombres']} {tutor['apellidos']}", cls="font-medium"), P(tutor["email"], cls=TextPresets.muted_sm))
                 if tutor else P("Todavía no tiene tutor(a) asignado. La Dirección de Carrera lo asigna.", cls="text-sm"),
                 H3("Reuniones registradas", cls="text-sm font-semibold mt-3"),
                 P(f"{len(reuniones)}: " + ", ".join(formato.fecha(f) for f in reuniones[:6]) + ("…" if len(reuniones) > 6 else ""),
                   cls="text-sm") if reuniones else P("Aún no hay reuniones registradas.", cls=TextPresets.muted_sm),
                 P("Solo se muestran las fechas: lo que se habló es confidencial.", cls=TextPresets.muted_sm)),
            Card(H3("Pedir una reunión", cls="text-base font-semibold mb-2"),
                 _formulario([errores] if errores else []) if tutor and not abiertas else
                 P("Ya tiene una solicitud abierta (abajo)." if abiertas else "Cuando tenga tutor(a) podrá pedirle una reunión.",
                   cls="text-sm")),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4"),
        Card(H3("Mis solicitudes", cls="text-base font-semibold"),
             Ul(*[_solicitud(s) for s in tutoria.solicitudes_de(externo)], cls="divide-y divide-border"))
        if tutoria.solicitudes_de(externo) else "", usuario=auth)


@rt(f"{BASE}/solicitud")
def post(auth, sess, tema: str = "", mensaje: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = tutoria.solicitar(externo, tema, mensaje)
    if errores:
        return pagina("Mi tutoría", P(errores[0], cls="text-sm text-destructive mb-4"), A("Volver", href=BASE,
                                                                                        cls="text-sm text-primary hover:underline"),
                      usuario=auth)
    add_toast(sess, "Se avisó a su tutor(a).", "success")
    return Redirect(BASE)


@rt(f"{BASE}/solicitud/{{sid}}/cancelar")
def post(auth, sess, sid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = tutoria.cancelar(sid, externo)
    if errores:
        return Response("No encontrado", status_code=404)
    add_toast(sess, "Solicitud cancelada.", "info")
    return Redirect(BASE)
