"""«Mis pendientes» y «Mi calendario» del investigador (PLAN §69, etapa 1). Solo lo propio: la persona sale de la sesión.
El menú lleva a los de toda la persona (`/pendientes` y `/calendario`, PLAN §73); estas direcciones muestran solo lo de
la investigación."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, P, Response
from monsterui.all import H2, TextPresets

from app.comun import calendario
from app.comun.componentes import agenda
from app.comun.componentes.layout import pagina
from app.investigacion import mis_pendientes as mp

rt = APIRouter()
PENDIENTES = "/investigacion/pendientes"
CALENDARIO = "/investigacion/calendario"


def _no_autorizado(auth) -> Response | None:
    if not auth.get("es_investigador"):
        return Response("No autorizado", status_code=403)


@rt(PENDIENTES)
def get(auth):
    if (error := _no_autorizado(auth)):
        return error
    hoy = date.today()
    return pagina(
        "Mis pendientes de investigación",
        H2("Mis pendientes de investigación"),
        P("Lo que espera de usted: la convocatoria de proyectos, lo que debe aprobar como responsable, el plan de sus "
          "proyectos, sus productos por actualizar y su perfil. Solo usted ve esta lista; no se guarda.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        *calendario.bloques(auth, PENDIENTES),   # p. ej., «Mi parte del plan de mejora», si ese módulo está activo
        agenda.lista_pendientes(mp.pendientes(auth["id"], hoy), hoy),
        P(A("Ver mi calendario", href=CALENDARIO, cls="text-sm text-primary hover:underline"), cls="mt-4"),
        usuario=auth, seccion="investigacion")


@rt(CALENDARIO)
def get(auth, dias: str = "90"):
    if (error := _no_autorizado(auth)):
        return error
    n, hoy = agenda.dias_de(dias), date.today()
    return pagina("Mi calendario de investigación", H2("Mi calendario de investigación"),
                  P("Sus fechas en un solo lugar: la convocatoria de proyectos, las actividades en que participa, el término "
                    "de sus proyectos, los meses previstos de su plan y los eventos a que lo convocan.",
                    cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  *agenda.calendario_por_meses(mp.eventos(auth["id"], hoy, hoy + timedelta(days=n)), hoy, n, CALENDARIO),
                  usuario=auth, seccion="investigacion")


@rt(f"{CALENDARIO}.ics")
def get(auth):
    if (error := _no_autorizado(auth)):
        return error
    hoy = date.today()
    contenido = calendario.ics(mp.eventos(auth["id"], hoy, hoy + timedelta(days=365)), titulo="Calendario de investigación")
    return Response(contenido.encode(), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="calendario-investigacion-tau.ics"'})
