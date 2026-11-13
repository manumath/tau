"""Evaluación docente, lado del estudiante (PLAN §68, etapa 5): ve el instrumento, evalúa cada paralelo en que está inscrito (una vez,
de forma anónima) y recibe el retorno. Las rutas `/estudiante/evaluacion*` no llevan el usuario en el registro de peticiones
(`registros.RUTAS_ANONIMAS`). La ficha sale de su cuenta; la inscripción, de la lista de curso por su RU."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, P, Redirect, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import evaluacion, gestiones
from app.academico.rutas.evaluacion import instrumento, reglas
from app.comun import formato
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.estudiantil.rutas.estudiante import _requiere

rt = APIRouter()
BASE = "/estudiante/evaluacion"


@rt(BASE)
def get(auth):
    externo, error = _requiere(auth)
    if error:
        return error
    e, cursos = evaluacion.por_evaluar(externo)
    visibles = [x for x in evaluacion.listar() if evaluacion.estado(x) in ("anunciada", "abierta")]
    pendientes = [c for c in cursos if not c["hecho"]]
    retornos = evaluacion.retornos_publicados()
    return pagina(
        "Evaluación docente", H2("Evaluación docente"),
        P("Una vez por semestre puede evaluar a los docentes de los paralelos en que está inscrito. Sus respuestas son anónimas.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        *[Card(H3(f"Evaluación de {gestiones.codigo(evaluacion.gestion_de(v))}", cls="text-base font-semibold"),
               P(f"Del {formato.fecha(v['abre_el'])} al {formato.fecha(v['cierra_el'])}.", cls=TextPresets.muted_sm),
               instrumento(v), cls="space-y-2 mb-4") for v in visibles],
        Card(H3("Paralelos para evaluar", cls="text-base font-semibold"),
             Ul(*[Li(Div(Div(Span(c["sigla"], cls="font-mono text-sm"), Span(f" {c['nombre']} · paralelo {c['paralelo']}", cls="text-sm")),
                         Div(c["docentes"] or "Sin docente titular", cls=TextPresets.muted_sm), cls="min-w-0 flex-1"),
                     insignia("Ya evaluó", "verde", icono="check") if c["hecho"] else
                     A("Evaluar", href=f"{BASE}/{c['oferta_id']}", cls="text-sm text-primary hover:underline"),
                     cls="flex items-center gap-3 py-2") for c in cursos], cls="divide-y divide-border") if cursos
             else P("No tiene paralelos para evaluar ahora." if e else "No hay una evaluación abierta.", cls="text-sm mt-1"),
             P(f"Le faltan {len(pendientes)}.", cls=(TextPresets.muted_sm, "mt-2")) if pendientes else "", cls="mb-4"),
        reglas(),
        *[Card(H3(f"Lo que hizo la Carrera con la evaluación de {gestiones.codigo(evaluacion.gestion_de(r))}", cls="text-base font-semibold"),
               *[P(x, cls="text-sm mt-1") for x in (r["retorno"] or "").splitlines() if x.strip()], cls="mt-4") for r in retornos],
        usuario=auth)


def _form(o, errores=()):
    return fh.Form(
        mensaje_error(*errores),
        *[Card(P(f"{n}. {texto}", cls="text-sm font-medium"),
               Div(*[fh.Label(Input(type="radio", name=clave, value=str(v), required=True, cls="uk-radio"), Span(f" {v}", cls="text-sm"),
                              title=t, cls="inline-flex items-center gap-1 mr-4") for v, t in evaluacion.ESCALA], cls="mt-2"),
               cls="mb-3") for n, (clave, texto) in enumerate(o["criterios"], start=1)],
        P("1 = totalmente en desacuerdo · 5 = totalmente de acuerdo.", cls=(TextPresets.muted_sm, "mb-3")),
        Button(UkIcon("send", height=14, width=14), "Enviar mi evaluación", type="submit", cls=ButtonT.primary,
               hx_confirm="Su evaluación es anónima y no se puede cambiar. ¿Enviarla?"),
        method="post", cls="space-y-2")


@rt(f"{BASE}/{{oid}}")
def get(auth, oid: int, errores: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    e, motivo = evaluacion.puede_evaluar(externo, oid)
    if motivo:
        return Response(motivo, status_code=403)
    from app.academico import oferta
    o = oferta.obtener(oid)
    return pagina(f"Evaluar {o['sigla']}", A(UkIcon("arrow-left", height=14, width=14), "Evaluación docente", href=BASE,
                                              cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  H2(f"{o['sigla']} · {o['nombre']} · paralelo {o['paralelo']}"),
                  P("Docente: " + (", ".join(f"{t['nombres']} {t['apellidos']}" for t in evaluacion.titulares(oid)) or "—")
                    + ". Su respuesta es anónima: no se enlaza con usted ni guarda la hora.", cls=(TextPresets.muted_sm, "mb-4")),
                  _form({**e}, [x for x in errores.split("|") if x]), usuario=auth)


@rt(f"{BASE}/{{oid}}")
async def post(auth, sess, oid: int, req):
    externo, error = _requiere(auth)
    if error:
        return error
    f = await req.form()
    errores = evaluacion.responder(externo, oid, dict(f))
    if errores:
        return Redirect(f"{BASE}/{oid}?errores={'|'.join(errores)}")
    add_toast(sess, "Gracias: su evaluación se registró de forma anónima.", "success")
    return Redirect(BASE)
