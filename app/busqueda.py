"""Búsqueda global (PLAN.md §48, paso 4): un campo en la barra de navegación busca personas, productos,
actividades, proyectos y asignaturas a la vez, y en «Usuarios» para quien administra cuentas.

Cada grupo respeta lo que la persona puede abrir: los proyectos, solo los que puede ver
(`proyectos.puede_ver`); las cuentas, solo con el permiso «ver_usuarios». Las sugerencias muestran pocos
resultados por grupo; «Ver todos» (o Enter) abre /buscar con más.
"""
from fasthtml.common import A, APIRouter, Div, H3, Li, P, Span, Ul
from monsterui.all import H2, TextPresets, UkIcon

from app.comun import permisos
from app.comun.componentes.layout import campo_busqueda, pagina
from app.comun.db import get_db, sin_tildes
from app.investigacion import actividades, perfiles, proyectos

rt = APIRouter()
MINIMO = 2
EN_SUGERENCIAS, EN_PAGINA = 4, 30


def _patron(q):
    return f"%{sin_tildes(q.strip())}%"


def _personas(q, auth, limite):
    return [{"texto": f"{p['nombres']} {p['apellidos']}", "href": f"/investigadores/{p['id']}",
             "detalle": " · ".join(x for x in (p.get("cargo"), p.get("unidad")) if x)}
            for p in perfiles.directorio(q)[:limite]]


def _cuentas(q, auth, limite):
    """Cuentas que no son de investigadores (esas ya salen en «Personas»), para quien ve los usuarios."""
    if not permisos.puede(auth, "ver_usuarios"):
        return []
    filas = get_db().q(
        """SELECT u.nombres, u.apellidos, u.email FROM usuario u
           WHERE NOT EXISTS (SELECT 1 FROM investigador i WHERE i.usuario_id = u.id)
             AND (sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p OR u.email LIKE :p)
           ORDER BY u.apellidos LIMIT :l""", {"p": _patron(q), "l": limite})
    return [{"texto": f"{f['nombres']} {f['apellidos']}", "href": f"/admin/usuarios?q={f['email']}",
             "detalle": f["email"]} for f in filas]


def _productos(q, auth, limite):
    filas = get_db().q(
        """SELECT p.id, p.titulo, p.anio, t.nombre AS tipo FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
           WHERE sin_tildes(p.titulo) LIKE :p OR p.doi = lower(:q) OR p.arxiv_id = :q
           ORDER BY p.anio DESC, p.id DESC LIMIT :l""", {"p": _patron(q), "q": q.strip(), "l": limite})
    return [{"texto": f["titulo"], "href": f"/productos/{f['id']}", "detalle": f"{f['anio']} · {f['tipo']}"}
            for f in filas]


def _actividades(q, auth, limite):
    filas = get_db().q(
        """SELECT a.id FROM actividad a WHERE sin_tildes(a.titulo) LIKE :p OR sin_tildes(a.institucion) LIKE :p
           ORDER BY a.fecha_inicio DESC LIMIT :l""", {"p": _patron(q), "l": limite})
    res = []
    for f in filas:
        a = actividades.obtener(f["id"])
        res.append({"texto": a["titulo"], "href": f"/actividades/{a['id']}",
                    "detalle": f"{actividades.fechas_texto(a)} · {a['tipo']}"})
    return res


def _proyectos(q, auth, limite):
    filas = get_db().q(
        """SELECT id, nombre, codigo, estado FROM proyecto
           WHERE sin_tildes(nombre) LIKE :p OR codigo LIKE :p ORDER BY fecha_inicio DESC, id DESC""",
        {"p": _patron(q)})
    visibles = [f for f in filas if proyectos.puede_ver(f["id"], auth)][:limite]
    return [{"texto": f["nombre"], "href": f"/proyectos/{f['id']}",
             "detalle": " · ".join(x for x in (f["codigo"], proyectos.ESTADOS.get(f["estado"], "")) if x)}
            for f in visibles]


def _asignaturas(q, auth, limite):
    """Llevan a la fila de la asignatura en el plan más reciente que la incluye."""
    filas = get_db().q(
        """SELECT a.sigla, a.nombre, MAX(pa.plan_id) AS plan_id FROM asignatura a
           JOIN plan_asignatura pa ON pa.asignatura_id = a.id
           WHERE a.sigla LIKE :p OR sin_tildes(a.nombre) LIKE :p
           GROUP BY a.id ORDER BY a.sigla LIMIT :l""", {"p": _patron(q), "l": limite})
    return [{"texto": f"{f['sigla']} · {f['nombre']}", "href": f"/docencia/planes/{f['plan_id']}#asignatura-{f['sigla']}",
             "detalle": "Plan de estudios"} for f in filas]


GRUPOS = (("Personas", "users", _personas), ("Cuentas", "user-cog", _cuentas), ("Productos", "book-open", _productos),
          ("Actividades", "calendar-days", _actividades), ("Proyectos", "folder-kanban", _proyectos),
          ("Asignaturas", "graduation-cap", _asignaturas))


def buscar(q: str, auth: dict, limite: int) -> list[dict]:
    """[{titulo, icono, items: [{texto, href, detalle}]}], solo los grupos con resultados."""
    if len(q.strip()) < MINIMO:
        return []
    grupos = [{"titulo": t, "icono": i, "items": f(q, auth, limite)} for t, i, f in GRUPOS]
    return [g for g in grupos if g["items"]]


def _item(x):
    return Li(A(Span(x["texto"], cls="font-medium"),
                Span(x["detalle"], cls=TextPresets.muted_sm) if x["detalle"] else "",
                href=x["href"], cls="flex flex-col px-3 py-2 hover:bg-muted focus:bg-muted focus:outline-none"))


@rt("/buscar/sugerencias")
def get(auth, q: str = ""):
    """Lo que se despliega bajo el campo de la barra de navegación."""
    if len(q.strip()) < MINIMO:
        return ""
    grupos = buscar(q, auth, EN_SUGERENCIAS)
    cuerpo = [Div(P(g["titulo"], cls="px-3 pt-2 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground"),
                  Ul(*[_item(x) for x in g["items"]])) for g in grupos] or \
        [P("Sin resultados.", cls=(TextPresets.muted_sm, "px-3 py-2"))]
    return Div(*cuerpo,
               A(f"Ver todos los resultados de «{q.strip()}»", href=f"/buscar?q={q.strip()}",
                 cls="block px-3 py-2 text-sm text-primary hover:underline border-t border-border"),
               cls="absolute right-0 z-50 mt-1 w-[26rem] max-w-[90vw] max-h-[70vh] overflow-y-auto rounded-md border "
                   "border-border bg-background shadow-lg text-left", role="region", aria_label="Resultados de la búsqueda")


@rt("/buscar")
def get(auth, q: str = ""):
    grupos = buscar(q, auth, EN_PAGINA)
    resultados = [Div(H3(UkIcon(g["icono"], height=16, width=16), f"{g['titulo']} ({len(g['items'])})",
                         cls="flex items-center gap-2 text-base font-semibold mb-1"),
                      Ul(*[_item(x) for x in g["items"]], cls="divide-y divide-border rounded-md border border-border"),
                      cls="space-y-1") for g in grupos]
    return pagina(
        "Buscar",
        H2("Buscar"),
        Div(campo_busqueda(q, sugerencias=False), cls="max-w-xl my-4"),
        P("Escriba al menos dos letras: busca personas, productos, actividades, proyectos y asignaturas."
          if len(q.strip()) < MINIMO else
          f"Sin resultados para «{q.strip()}»." if not grupos else
          f"Hasta {EN_PAGINA} resultados por grupo.", cls=(TextPresets.muted_sm, "mb-4")),
        Div(*resultados, cls="space-y-6"),
        usuario=auth)
