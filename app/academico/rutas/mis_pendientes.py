"""«Mis pendientes» y «Mi calendario» del docente (PLAN §68, etapa 1). Solo lo propio: la persona sale de la sesión.
El menú lleva a los de toda la persona (`/pendientes` y `/calendario`, PLAN §73); estas direcciones muestran solo lo de
la docencia."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, P, Response
from monsterui.all import H2, TextPresets

from app.academico import docente
from app.comun import calendario
from app.comun.componentes import agenda
from app.comun.componentes.layout import pagina

rt = APIRouter()
PENDIENTES = "/docencia/pendientes"
CALENDARIO = "/docencia/calendario"


@rt(PENDIENTES)
def get(auth):
    hoy = date.today()
    return pagina(
        "Mis pendientes",
        H2("Mis pendientes"),
        P("Lo que espera de usted: informes y notas de tribunales, vistos buenos como tutor(a), solicitudes de reunión y de "
          "tema, y su periodo de vínculo. Solo usted ve esta lista; no se guarda.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        *calendario.bloques(auth, PENDIENTES),   # p. ej., «Mi parte del plan de mejora», si ese módulo está activo
        agenda.lista_pendientes(docente.pendientes(auth["id"], hoy), hoy),
        P(A("Ver mi calendario", href=CALENDARIO, cls="text-sm text-primary hover:underline"), cls="mt-4"),
        usuario=auth, seccion="docencia")


@rt(CALENDARIO)
def get(auth, dias: str = "90"):
    n, hoy = agenda.dias_de(dias), date.today()
    return pagina("Mi calendario", H2("Mi calendario"),
                  P("Sus fechas en un solo lugar: el semestre, los plazos y las defensas de los trámites de grado en que "
                    "participa, las reuniones de tutoría programadas, los eventos a que lo convocan y el término de su vínculo.",
                    cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  *agenda.calendario_por_meses(docente.eventos(auth["id"], hoy, hoy + timedelta(days=n)), hoy, n, CALENDARIO),
                  usuario=auth, seccion="docencia")


@rt(f"{CALENDARIO}.ics")
def get(auth):
    hoy = date.today()
    contenido = calendario.ics(docente.eventos(auth["id"], hoy, hoy + timedelta(days=365)), titulo="Calendario docente")
    return Response(contenido.encode(), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="calendario-docente-tau.ics"'})
