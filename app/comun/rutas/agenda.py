"""«Mis pendientes» y «Mi calendario» de toda la persona (PLAN §73): lo de la docencia y lo de la investigación juntos, con
lo que aporta cada módulo activo. Solo lo propio: la persona sale de la sesión (`auth["id"]`); no se guarda nada."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, P, Response
from monsterui.all import H2, TextPresets

from app.comun import calendario
from app.comun.componentes import agenda
from app.comun.componentes.layout import pagina

rt = APIRouter()
PENDIENTES = "/pendientes"
CALENDARIO = "/calendario"


def _ambitos(auth) -> list[str]:
    """La docencia vale para cualquiera del personal (sin vínculo ni materias no hay nada que mostrar); la investigación,
    solo para quien tiene perfil de investigador."""
    return ["docente", *(["investigador"] if auth.get("es_investigador") else [])]


def _sin_repetir(filas: list[dict], claves: tuple) -> list[dict]:
    """Un evento a que convocan a la persona llega por los dos ámbitos: se muestra una vez."""
    vistos, res = set(), []
    for f in filas:
        marca = tuple(f[c] for c in claves)
        if marca not in vistos:
            vistos.add(marca)
            res.append(f)
    return res


def pendientes(auth, hoy: date) -> list[dict]:
    todos = [p for a in _ambitos(auth) for p in calendario.pendientes_de(a, auth["id"], hoy)]
    return _sin_repetir(sorted(todos, key=lambda p: (p["cuando"] is None, p["cuando"] or "", p["titulo"])),
                        ("titulo", "cuando", "href"))


def eventos(auth, desde: date, hasta: date) -> list[dict]:
    todos = [e for a in _ambitos(auth) for e in calendario.eventos_de(a, auth["id"], desde, hasta)]
    return _sin_repetir(sorted(todos, key=lambda e: (e["fecha"], e["hora"], e["titulo"])), ("fecha", "hora", "titulo", "href"))


@rt(PENDIENTES)
def get(auth):
    hoy = date.today()
    return pagina(
        "Mis pendientes",
        H2("Mis pendientes"),
        P("Lo que espera de usted, en un solo lugar: su docencia, sus proyectos y productos, los trámites y tribunales en "
          "que participa y su parte del plan de mejora. Solo usted ve esta lista; no se guarda.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        *calendario.bloques(auth, PENDIENTES),
        agenda.lista_pendientes(pendientes(auth, hoy), hoy),
        P(A("Ver mi calendario", href=CALENDARIO, cls="text-sm text-primary hover:underline"), cls="mt-4"),
        usuario=auth)


@rt(CALENDARIO)
def get(auth, dias: str = "90"):
    n, hoy = agenda.dias_de(dias), date.today()
    return pagina("Mi calendario", H2("Mi calendario"),
                  P("Sus fechas en un solo lugar: el semestre, la convocatoria de proyectos, los plazos y las defensas de los "
                    "trámites en que participa, sus actividades, las reuniones programadas y los eventos a que lo convocan.",
                    cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  *agenda.calendario_por_meses(eventos(auth, hoy, hoy + timedelta(days=n)), hoy, n, CALENDARIO),
                  usuario=auth)


@rt(f"{CALENDARIO}.ics")
def get(auth):
    hoy = date.today()
    contenido = calendario.ics(eventos(auth, hoy, hoy + timedelta(days=365)), titulo="Mi calendario")
    return Response(contenido.encode(), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="calendario-tau.ics"'})
