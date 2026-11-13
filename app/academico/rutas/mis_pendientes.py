"""«Mis pendientes» y «Mi calendario» del docente (PLAN §68, etapa 1). Solo lo propio: la persona sale de la sesión."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, Div, Li, P, Response, Span, Ul
from monsterui.all import H2, H3, Card, TextPresets, UkIcon

from app.academico import docente
from app.estudiantil import calendario
from app.comun import formato
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia

rt = APIRouter()
PENDIENTES = "/docencia/pendientes"
CALENDARIO = "/docencia/calendario"
TONOS = {"grado": "verde", "auxiliatura": "ambar", "tutoria": "gris", "tema": "azul", "vinculo": "ambar", "gestion": "gris",
         "evento": "azul"}
SITUACIONES = {"vencido": ("Vencido", "rojo"), "proximo": ("Próximo", "ambar")}
PLAZOS = {"30": 30, "90": 90, "180": 180}
MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
         "Diciembre")


def _fila(p: dict, hoy: date):
    s = docente.situacion(p, hoy)
    titulo = A(p["titulo"], href=p["href"], cls="hover:underline") if p["href"] else p["titulo"]
    return Li(Div(Div(Div(titulo, cls="text-sm font-medium"),
                      Div(" · ".join(x for x in (p["detalle"], f"vence el {formato.fecha(p['cuando'])}" if p["cuando"] else "")
                                     if x), cls=TextPresets.muted_sm), cls="min-w-0 flex-1"),
                  insignia(*SITUACIONES[s]) if s in SITUACIONES else "",
                  insignia(docente.TIPOS[p["tipo"]], TONOS[p["tipo"]]), cls="flex items-start gap-3 py-2"))


@rt(PENDIENTES)
def get(auth):
    hoy = date.today()
    lista = docente.pendientes(auth["id"], hoy)
    return pagina(
        "Mis pendientes",
        H2("Mis pendientes"),
        P("Lo que espera de usted: informes y notas de tribunales, vistos buenos como tutor(a), solicitudes de reunión y de "
          "tema, y su periodo de vínculo. Solo usted ve esta lista; no se guarda.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(Ul(*[_fila(p, hoy) for p in lista], cls="divide-y divide-border")) if lista
        else Card(P(UkIcon("circle-check", height=16, width=16, cls="inline mr-1"), "No tiene nada pendiente.", cls="text-sm")),
        P(A("Ver mi calendario", href=CALENDARIO, cls="text-sm text-primary hover:underline"), cls="mt-4"),
        usuario=auth, seccion="docencia")


@rt(CALENDARIO)
def get(auth, dias: str = "90"):
    n = PLAZOS.get(dias, 90)
    hoy = date.today()
    meses: dict = {}
    for e in docente.eventos(auth["id"], hoy, hoy + timedelta(days=n)):
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
                                        insignia(docente.TIPOS[e["tipo"]], TONOS[e["tipo"]]),
                                        cls="flex items-start gap-3 py-2")) for e in es], cls="divide-y divide-border")))
    filtros = Div(*[A(f"{k} días", href=f"{CALENDARIO}?dias={k}", aria_current="true" if k == str(n) else None,
                      cls="text-sm rounded-full border px-3 py-1 " + ("bg-primary text-primary-foreground border-primary"
                                                                        if k == str(n) else "hover:bg-muted")) for k in PLAZOS],
                   A(UkIcon("download", height=14, width=14), "Llevar a mi calendario (.ics)", href=f"{CALENDARIO}.ics",
                     cls="inline-flex items-center gap-1 text-sm text-primary hover:underline ml-auto"),
                   cls="flex flex-wrap items-center gap-2 mb-4")
    return pagina("Mi calendario", H2("Mi calendario"),
                  P("Sus fechas en un solo lugar: el semestre, los plazos y las defensas de los trámites de grado en que "
                    "participa, las reuniones de tutoría programadas, los eventos a que lo convocan y el término de su vínculo.",
                    cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  filtros, *(bloques or [Card(P("No hay fechas en este periodo.", cls="text-sm"))]),
                  usuario=auth, seccion="docencia")


@rt(f"{CALENDARIO}.ics")
def get(auth):
    hoy = date.today()
    contenido = calendario.ics(docente.eventos(auth["id"], hoy, hoy + timedelta(days=365)), titulo="Calendario docente")
    return Response(contenido.encode(), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="calendario-docente-tau.ics"'})
