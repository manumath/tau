"""Tablero personal. En esta iteración muestra los módulos y su fase de desarrollo."""
from fasthtml.common import A, APIRouter, Div, P, Span
from monsterui.all import H2, H4, Card, Grid, Label, LabelT, TextPresets, UkIcon

from app.components.layout import pagina

rt = APIRouter()

MODULOS = [
    ("user-round", "Mi perfil", "Datos básicos, ORCID, MathSciNet, zbMATH y áreas MSC.", 2, None),
    ("calendar-days", "Mis actividades", "Seminarios, congresos, visitas y escuelas.", 3, None),
    ("book-open", "Mis productos", "Artículos indexados o arbitrados, reportes de investigación, "
                                   "libros y presentaciones.", 3, None),
    ("folder-kanban", "Mis proyectos", "Proyectos en los que participa y propuestas pendientes.",
     4, None),
]
MODULOS_ADMIN = [
    ("users", "Usuarios", "Crear cuentas, restablecer contraseñas y desactivar accesos.", 1,
     "/admin/usuarios"),
]


def _tarjeta(icono, titulo, descripcion, fase, href):
    disponible = href is not None
    contenido = Div(
        Div(UkIcon(icono, height=22, width=22, cls="text-primary"),
            Label("Disponible" if disponible else f"Fase {fase}",
                  cls=LabelT.primary if disponible else LabelT.secondary),
            cls="flex items-center justify-between"),
        H4(titulo, cls="mt-3"),
        P(descripcion, cls=TextPresets.muted_sm),
    )
    tarjeta = Card(contenido, cls="h-full" + ("" if disponible else " opacity-70"))
    return A(tarjeta, href=href, cls="block hover:shadow-md transition") if disponible else tarjeta


@rt("/")
def get(auth):
    modulos = (MODULOS_ADMIN if auth["es_admin"] else []) + MODULOS
    return pagina(
        "Inicio",
        Div(H2(f"Hola, {auth['nombres']}"),
            P(Span("Primera iteración del portal: acceso y administración de cuentas. "),
              "Los módulos marcados con su fase se habilitarán en las próximas entregas.",
              cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Grid(*[_tarjeta(*m) for m in modulos], cols_sm=1, cols_md=2, cols_lg=3, gap=4),
        usuario=auth, seccion="inicio")
