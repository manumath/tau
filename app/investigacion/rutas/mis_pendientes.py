"""«Mis pendientes» y «Mi calendario» del investigador (PLAN §69, etapa 1). Solo lo propio: la persona sale de la sesión."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, Div, Li, P, Response, Span, Ul
from monsterui.all import H2, H3, Card, TextPresets, UkIcon

from app.comun import formato
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.calidad.rutas.actividades_mejora import mi_parte
from app.estudiantil import calendario
from app.investigacion import mis_pendientes as mp

rt = APIRouter()
PENDIENTES = "/investigacion/pendientes"
CALENDARIO = "/investigacion/calendario"
TONOS = {"propuesta": "azul", "proyecto": "verde", "plan": "ambar", "producto": "gris", "perfil": "gris", "carga": "ambar",
         "actividad": "azul", "evento": "azul", "acceso": "verde", "mejora": "azul"}
SITUACIONES = {"vencido": ("Vencido", "rojo"), "proximo": ("Próximo", "ambar")}
PLAZOS = {"30": 30, "90": 90, "180": 180}
MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
         "Diciembre")


def _no_autorizado(auth) -> Response | None:
    if not auth.get("es_investigador"):
        return Response("No autorizado", status_code=403)


def _fila(p: dict, hoy: date):
    s = mp.situacion(p, hoy)
    titulo = A(p["titulo"], href=p["href"], cls="hover:underline") if p["href"] else p["titulo"]
    return Li(Div(Div(Div(titulo, cls="text-sm font-medium"),
                      Div(" · ".join(x for x in (p["detalle"], f"vence el {formato.fecha(p['cuando'])}" if p["cuando"] else "")
                                     if x), cls=TextPresets.muted_sm), cls="min-w-0 flex-1"),
                  insignia(*SITUACIONES[s]) if s in SITUACIONES else "",
                  insignia(mp.TIPOS[p["tipo"]], TONOS[p["tipo"]]), cls="flex items-start gap-3 py-2"))


@rt(PENDIENTES)
def get(auth):
    if (error := _no_autorizado(auth)):
        return error
    hoy = date.today()
    lista = mp.pendientes(auth["id"], hoy)
    return pagina(
        "Mis pendientes de investigación",
        H2("Mis pendientes de investigación"),
        P("Lo que espera de usted: la convocatoria de proyectos, lo que debe aprobar como responsable, el plan de sus "
          "proyectos, sus productos por actualizar y su perfil. Solo usted ve esta lista; no se guarda.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        mi_parte(auth, PENDIENTES),
        Card(Ul(*[_fila(p, hoy) for p in lista], cls="divide-y divide-border")) if lista
        else Card(P(UkIcon("circle-check", height=16, width=16, cls="inline mr-1"), "No tiene nada pendiente.", cls="text-sm")),
        P(A("Ver mi calendario", href=CALENDARIO, cls="text-sm text-primary hover:underline"), cls="mt-4"),
        usuario=auth, seccion="investigacion")


@rt(CALENDARIO)
def get(auth, dias: str = "90"):
    if (error := _no_autorizado(auth)):
        return error
    n = PLAZOS.get(dias, 90)
    hoy = date.today()
    meses: dict = {}
    for e in mp.eventos(auth["id"], hoy, hoy + timedelta(days=n)):
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
                                        insignia(mp.TIPOS[e["tipo"]], TONOS[e["tipo"]]),
                                        cls="flex items-start gap-3 py-2")) for e in es], cls="divide-y divide-border")))
    filtros = Div(*[A(f"{k} días", href=f"{CALENDARIO}?dias={k}", aria_current="true" if k == str(n) else None,
                      cls="text-sm rounded-full border px-3 py-1 " + ("bg-primary text-primary-foreground border-primary"
                                                                        if k == str(n) else "hover:bg-muted")) for k in PLAZOS],
                   A(UkIcon("download", height=14, width=14), "Llevar a mi calendario (.ics)", href=f"{CALENDARIO}.ics",
                     cls="inline-flex items-center gap-1 text-sm text-primary hover:underline ml-auto"),
                   cls="flex flex-wrap items-center gap-2 mb-4")
    return pagina("Mi calendario de investigación", H2("Mi calendario de investigación"),
                  P("Sus fechas en un solo lugar: la convocatoria de proyectos, las actividades en que participa, el término "
                    "de sus proyectos, los meses previstos de su plan y los eventos a que lo convocan.",
                    cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  filtros, *(bloques or [Card(P("No hay fechas en este periodo.", cls="text-sm"))]),
                  usuario=auth, seccion="investigacion")


@rt(f"{CALENDARIO}.ics")
def get(auth):
    if (error := _no_autorizado(auth)):
        return error
    hoy = date.today()
    contenido = calendario.ics(mp.eventos(auth["id"], hoy, hoy + timedelta(days=365)), titulo="Calendario de investigación")
    return Response(contenido.encode(), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="calendario-investigacion-tau.ics"'})
