"""Lista de proyectos, con la convocatoria institucional y el contador de pendientes."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, H3, Li, P, Span, Ul
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import permisos
from app.investigacion import proyectos
from app.comun.componentes.layout import ID_MODAL, pagina
from app.comun.componentes.registros import insignia
from app.investigacion.rutas import propuestas as ui_propuestas
from app.investigacion.rutas.proyectos.base import _periodo, insignia_contador, insignia_estado, insignia_tipo

rt = APIRouter()


# --- Lista de proyectos ---------------------------------------------------------------------------

def tarjeta(p):
    extra = [insignia_tipo(p), insignia_estado(p)]
    if p.get("mi_rol"):
        extra.append(insignia(proyectos.ROLES[p["mi_rol"]] + ("" if p["vigente"] else " (anterior)"),
                              "azul", icono="user-round"))
    pendientes = proyectos.n_pendientes(p["id"]) if p.get("mi_rol") in proyectos.ROLES_RESPONSABLES \
        and p.get("vigente") else 0
    if pendientes:
        extra.append(insignia(f"{pendientes} por revisar", "ambar", icono="inbox"))
    return A(Card(
        Div(Span(p["codigo"] or "", cls="font-mono text-xs text-muted-foreground"),
            Span(_periodo(p) or "", cls=TextPresets.muted_sm), cls="flex justify-between"),
        H3(p["nombre"], cls="text-base font-semibold mt-1"),
        P(f"{p['n_part']} participante{'s' if p['n_part'] != 1 else ''}"
          + (f" · {p['fuente_financiamiento']}" if p["fuente_financiamiento"] else ""),
          cls=TextPresets.muted_sm),
        Div(*extra, cls="flex flex-wrap gap-1.5 mt-2"),
        cls="h-full hover:shadow-md transition"), href=f"/proyectos/{p['id']}", cls="block")


def seccion_propuestas(uid):
    propias = proyectos.mis_propuestas(uid)
    if not propias:
        return ""
    filas = []
    for v in propias:
        href = f"/{'actividades' if v['tipo'] == 'actividad' else 'productos'}/{v['registro_id']}"
        filas.append(Li(
            Div(A(v["titulo"], href=href, cls="font-medium hover:underline"),
                Span(f" → {v['proyecto']}", cls=TextPresets.muted_sm)),
            insignia("Pendiente", "ambar", icono="clock") if v["estado"] == "pendiente"
            else Div(insignia("Rechazado", "rojo", icono="circle-x"),
                     Span(f" «{v['comentario']}» — edítelo y guárdelo para volver a proponerlo.",
                          cls="text-sm")),
            cls="py-2 space-y-1"))
    return Card(H3("Mis propuestas en revisión", cls="text-base font-semibold"),
                Ul(*filas, cls="divide-y divide-border"), cls="mt-8")


def _filtro_tipo(tipo):
    opciones = [("", "Todos")] + list(proyectos.TIPOS.items())
    return Div(*[A(t, href=f"/proyectos?tipo={v}#todos" if v else "/proyectos#todos",
                   cls="text-sm px-3 py-1 rounded-full border " +
                       ("border-primary bg-primary/10 text-primary" if v == tipo else "border-border hover:bg-muted"))
                 for v, t in opciones], cls="flex gap-2 mb-4")


@rt("/proyectos")
def get(auth, q: str = "", tipo: str = ""):
    todos = permisos.puede(auth, "ver_todos_los_proyectos")
    tipo = tipo if tipo in proyectos.TIPOS else ""
    mios = proyectos.de_investigador(auth["id"])
    bloques = [
        Div(Div(H2("Proyectos"),
                P("Proyectos de investigación en que participa. Desde el formulario de una actividad o "
                  "un producto puede proponerlo a sus proyectos; el responsable lo aprueba.",
                  cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=16, width=16), "Nuevo proyecto individual", cls=ButtonT.primary,
                   hx_get="/proyectos/nuevo", hx_target=f"#{ID_MODAL}") if proyectos.puede_crear(auth) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        ui_propuestas.aviso_convocatoria(auth) if auth["es_investigador"] else "",
        H3("Mis proyectos", cls="text-lg font-semibold mb-3") if todos and auth["es_investigador"] else "",
        fh.Div(*[tarjeta(p) for p in mios], cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4")
        if mios else P("No participa en proyectos todavía.", cls=TextPresets.muted_sm)
        if auth["es_investigador"] else "",
        seccion_propuestas(auth["id"]),
        ui_propuestas.seccion_mis_propuestas(auth) if auth["es_investigador"] else "",
    ]
    if todos:
        todos = [p for p in proyectos.todos(q, tipo) if p["id"] not in {m["id"] for m in mios}]
        bloques += [H3("Todos los proyectos del instituto", id="todos", cls="text-lg font-semibold mt-10 mb-1"),
                    P("Se ven todos, pero solo los gestionan sus responsables."
                      + (" Desde la ficha de un proyecto puede reasignar al responsable."
                         if proyectos.puede_reasignar(auth) else ""), cls=(TextPresets.muted_sm, "mb-3")),
                    _filtro_tipo(tipo),
                    fh.Div(*[tarjeta(p) for p in todos],
                           cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4")
                    if todos else P("No hay otros proyectos.", cls=TextPresets.muted_sm)]
    return pagina("Proyectos", *bloques, usuario=auth, seccion="proyectos")


@rt("/proyectos/pendientes/contador")
def get(auth):
    """Contador de la navegación: propuestas que esta persona debe revisar."""
    n = proyectos.n_pendientes_para(auth) if auth["es_investigador"] else 0
    return insignia_contador(n)
