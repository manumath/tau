"""«Encuestas» del estudiante (PLAN §67, etapa 7): las que tiene por responder (con su enlace personal) y el retorno de las que ya
cerraron: lo que encontró la Carrera, lo que hará y los resultados agregados (sin respuestas abiertas)."""
from fasthtml.common import A, APIRouter, Div, Li, P, Span, Ul
from monsterui.all import H2, H3, Card, Progress, TextPresets

from app.comun import formato
from app.comun.componentes.layout import pagina
from app.estudiantil import encuestas
from app.estudiantil.rutas.estudiante import _requiere

rt = APIRouter()
BASE = "/estudiante/encuestas"


def _pregunta(p):
    q = p["pregunta"]
    if q["tipo"] == "escala":
        return Div(Span(q["texto"], cls="text-sm font-medium"),
                   Div(f"Promedio {formato.numero(p['promedio'], 1)} de 5 · {p['n']} respuesta(s)", cls=TextPresets.muted_sm)
                   if p.get("promedio") is not None else "",
                   Progress(value=p["promedio"], max=5, aria_label=q["texto"]) if p.get("promedio") is not None else "",
                   cls="space-y-1")
    total = sum(p["conteo"].values()) or 1
    return Div(Span(q["texto"], cls="text-sm font-medium"),
               Ul(*[Li(f"{encuestas.texto_valor(q, k)}: {round(100 * v / total)} %", cls="text-sm") for k, v in p["conteo"].items()]),
               cls="space-y-1")


@rt(BASE)
def get(auth):
    externo, error = _requiere(auth)
    if error:
        return error
    pendientes = encuestas.por_responder(externo)
    retornos = encuestas.retornos_para(externo)
    return pagina(
        "Encuestas", H2("Encuestas"),
        P("Las encuestas de la Carrera a las que lo invitaron. Sus respuestas ayudan a mejorarla: aquí también ve qué encontró la "
          "Carrera y qué hará.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(H3("Por responder", cls="text-base font-semibold mb-1"),
             Ul(*[Li(A(e["titulo"], href=f"/encuesta/{e['token']}", cls="text-sm font-medium text-primary hover:underline"),
                     Span(f" · hasta el {formato.fecha(e['cierra_el'])}" if e["cierra_el"] else "", cls=TextPresets.muted_sm),
                     cls="py-1.5") for e in pendientes], cls="divide-y divide-border")) if pendientes else
        Card(P("No tiene encuestas por responder.", cls="text-sm")),
        *[Card(H3(e["titulo"], cls="text-base font-semibold"),
               P(f"Participaron {e['n']} de {e['invitadas']} personas invitadas.", cls=TextPresets.muted_sm),
               Div(H3("Lo que encontramos", cls="text-sm font-semibold mt-2"),
                   P(e["retorno"], cls="text-sm whitespace-pre-line")),
               Div(H3("Lo que haremos", cls="text-sm font-semibold mt-2"),
                   P(e["acciones"], cls="text-sm whitespace-pre-line")) if e["acciones"] else "",
               Div(H3("Resultados", cls="text-sm font-semibold mt-3 mb-1"),
                   *[_pregunta(p) for p in e["preguntas"]], cls="space-y-3") if e["preguntas"] and not e["oculto"] else "",
               cls="mt-4") for e in retornos], usuario=auth)
