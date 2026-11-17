"""Calendario académico del estudiante (PLAN §67, etapa 2): sus fechas y un archivo .ics para su teléfono."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, Div, Li, P, Response, Span, Ul
from monsterui.all import H2, H3, Card, TextPresets, UkIcon

from app.comun import formato
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.estudiantil import calendario
from app.estudiantil.rutas.estudiante import _requiere

rt = APIRouter()
BASE = "/estudiante/calendario"
TONOS = {"gestion": "gris", "evento": "azul", "auxiliatura": "ambar", "grado": "verde", "oportunidad": "azul",
         "tutoria": "gris", "encuesta": "gris"}
PLAZOS = {"30": 30, "90": 90, "180": 180}
MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
         "Diciembre")


@rt(BASE)
def get(auth, dias: str = "90"):
    externo, error = _requiere(auth)
    if error:
        return error
    n = PLAZOS.get(dias, 90)
    hoy = date.today()
    lista = calendario.eventos(externo, hoy, hoy + timedelta(days=n))
    meses: dict = {}
    for e in lista:
        meses.setdefault(e["fecha"][:7], []).append(e)
    bloques = []
    for mes, es in meses.items():
        f = date.fromisoformat(mes + "-01")
        bloques.append(Card(H3(f"{MESES[f.month - 1]} de {f.year}", cls="text-base font-semibold mb-2"),
                            Ul(*[Li(Div(Span(formato.fecha(e["fecha"], anio=False) if e["fecha"] != hoy.isoformat() else "Hoy",
                                             cls="text-sm font-medium w-24 shrink-0"),
                                        Div(Div(A(e["titulo"], href=e["href"], cls="hover:underline") if e["href"]
                                                else e["titulo"], cls="text-sm"),
                                            Div(" · ".join(x for x in (e["hora"], e["detalle"]) if x), cls=TextPresets.muted_sm),
                                            cls="min-w-0 flex-1"),
                                        insignia(calendario.TIPOS[e["tipo"]], TONOS[e["tipo"]]),
                                        cls="flex items-start gap-3 py-2")) for e in es], cls="divide-y divide-border")))
    filtros = Div(*[A(f"{k} días", href=f"{BASE}?dias={k}", aria_current="true" if k == str(n) else None,
                      cls="text-sm rounded-full border px-3 py-1 " + ("bg-primary text-primary-foreground border-primary"
                                                                        if k == str(n) else "hover:bg-muted")) for k in PLAZOS],
                   A(UkIcon("download", height=14, width=14), "Llevar a mi calendario (.ics)", href=f"{BASE}.ics",
                     cls="inline-flex items-center gap-1 text-sm text-primary hover:underline ml-auto"),
                   cls="flex flex-wrap items-center gap-2 mb-4")
    return pagina("Calendario académico", H2("Calendario académico"),
                  P("Sus fechas en un solo lugar: el semestre, las convocatorias, los eventos a los que lo convocan y los "
                    "plazos y defensas de su proyecto de grado.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  filtros,
                  *(bloques or [Card(P("No hay fechas en este periodo.", cls="text-sm"))]), usuario=auth)


@rt(f"{BASE}.ics")
def get(auth):
    externo, error = _requiere(auth)
    if error:
        return error
    hoy = date.today()
    contenido = calendario.ics(calendario.eventos(externo, hoy, hoy + timedelta(days=365)))
    return Response(contenido.encode(), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="calendario-tau.ics"'})
