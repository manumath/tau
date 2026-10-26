"""Responder una encuesta con el enlace personal (PLAN §49 y §50). Sin cuenta ni sesión: el enlace es la
credencial. Abrir el enlace no lo gasta; se gasta al enviar la respuesta."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, P, Span
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, TextPresets

from app.comun import config
from app.comun.componentes.layout import logotipo, mensaje_error, pagina
from app.estudiantil import encuestas

rt = APIRouter()


def _tarjeta(titulo, *contenido):
    return pagina(titulo, Card(
        Div(*logotipo("w-52"), cls="flex justify-center mb-2"), H2(titulo, cls="text-center text-xl"), *contenido,
        cls="w-full max-w-2xl space-y-4"))


def _invalido():
    return _tarjeta("Enlace no válido", P("El enlace ya se usó, la encuesta se cerró o el enlace no es correcto. Si cree que "
                                          "es un error, escriba a la Dirección de Carrera.", cls=TextPresets.muted_sm))


def _campo(q, previo):
    nombre = f"p{q['id']}"
    marca = Span(" *", cls="text-destructive", aria_hidden="true") if q["obligatoria"] else ""
    titulo = H3(q["texto"], marca, cls="text-base font-medium")

    def opcion(tipo, valor, texto):
        return fh.Label(fh.Input(type=tipo, name=nombre, value=valor, checked=valor in previo,
                                 cls="uk-radio" if tipo == "radio" else "uk-checkbox"),
                        Span(texto), cls="flex items-center gap-2 text-sm")
    if q["tipo"] == "escala":
        cuerpo = Div(*[opcion("radio", str(n), f"{n} · {t}") for n, t in encuestas.ESCALA], cls="space-y-1")
    elif q["tipo"] == "si_no":
        cuerpo = Div(opcion("radio", "si", "Sí"), opcion("radio", "no", "No"), cls="space-y-1")
    elif q["tipo"] == "opcion":
        cuerpo = Div(*[opcion("radio", o, o) for o in q["opciones"]], cls="space-y-1")
    elif q["tipo"] == "multiple":
        cuerpo = Div(*[opcion("checkbox", o, o) for o in q["opciones"]], cls="space-y-1")
        cuerpo = Div(P("Puede marcar varias.", cls=TextPresets.muted_sm), cuerpo)
    else:
        cuerpo = fh.Textarea(previo[0] if previo else "", name=nombre, rows="3", maxlength=str(encuestas.MAX_TEXTO),
                             cls="uk-textarea", aria_label=q["texto"])
    return Div(titulo, cuerpo, cls="space-y-2")


def _formulario(token, e, errores=(), previas=None):
    previas = previas or {}
    qs = encuestas.preguntas(e["id"])
    aviso = ("Es anónima: sus respuestas no se asocian con su nombre ni con su correo." if e["anonima"]
             else "Sus respuestas se asocian con su nombre.")
    return _tarjeta(
        e["titulo"], P(e["descripcion"], cls="text-sm") if e["descripcion"] else "",
        P(aviso, cls=(TextPresets.muted_sm, "text-center")),
        Form(mensaje_error(*errores), *[_campo(q, previas.get(q["id"], [])) for q in qs],
             P("* Respuesta obligatoria.", cls=TextPresets.muted_sm),
             Button("Enviar respuestas", type="submit", cls=(ButtonT.primary, "w-full")),
             method="post", action=f"/encuesta/{token}", cls="space-y-6"))


@rt("/encuesta/{token}")
def get(token: str):
    v = encuestas.invitacion_vigente(token)
    return _formulario(token, v[1]) if v else _invalido()


@rt("/encuesta/{token}")
async def post(req, token: str):
    v = encuestas.invitacion_vigente(token)
    if not v:
        return _invalido()
    form = await req.form()
    qs = encuestas.preguntas(v[1]["id"])
    crudo = {q["id"]: [str(x) for x in form.getlist(f"p{q['id']}")] for q in qs}
    errores = encuestas.responder(token, crudo)
    if errores:
        return _formulario(token, v[1], errores, crudo)
    return _tarjeta("¡Gracias!", P(f"Recibimos sus respuestas. Su participación ayuda a mejorar la Carrera de Matemática "
                                   f"({config.NOMBRE_SISTEMA}).", cls="text-sm text-center"))
