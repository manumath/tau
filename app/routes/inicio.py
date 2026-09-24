"""Tablero personal: accesos a los módulos y estado del perfil."""
from datetime import date

from fasthtml.common import A, APIRouter, Div, P, Span
from monsterui.all import H2, H4, Card, Grid, Label, LabelT, Progress, TextPresets, UkIcon

from app import actividades, perfiles, productos
from app.components.layout import pagina

rt = APIRouter()

# (icono, título, descripción, fase en que se habilita, enlace si ya está disponible)
MODULOS_FUTUROS = [
    ("folder-kanban", "Mis proyectos", "Proyectos en los que participa y propuestas pendientes.",
     4, None),
]
MODULO_DIRECTORIO = ("book-user", "Investigadores",
                     "Directorio interno: busque colegas por nombre o área MSC.", 2, "/investigadores")
MODULO_USUARIOS = ("users", "Usuarios", "Crear cuentas, restablecer contraseñas y desactivar accesos.",
                   1, "/admin/usuarios")


def _tarjeta(icono, titulo, descripcion, fase, href, extra=None):
    disponible = href is not None
    contenido = Div(
        Div(UkIcon(icono, height=22, width=22, cls="text-primary"),
            Label("Disponible" if disponible else f"Fase {fase}",
                  cls=LabelT.primary if disponible else LabelT.secondary),
            cls="flex items-center justify-between"),
        H4(titulo, cls="mt-3"),
        P(descripcion, cls=TextPresets.muted_sm),
        extra or "",
    )
    tarjeta = Card(contenido, cls="h-full" + ("" if disponible else " opacity-70"))
    return A(tarjeta, href=href, cls="block hover:shadow-md transition") if disponible else tarjeta


def _cifra(valor, texto):
    return Div(Span(str(valor), cls="text-2xl font-semibold"), Span(texto, cls=TextPresets.muted_sm),
               cls="flex flex-col")


def _tarjetas_produccion(uid):
    anio = date.today().year
    prods = productos.de_investigador(uid)
    del_anio = [p for p in prods if p["anio"] == anio]
    acts = [a for a in actividades.de_investigador(uid) if a["fecha_inicio"].startswith(str(anio))]
    extra_p = Div(_cifra(len(del_anio), f"en {anio}"),
                  _cifra(sum(productos.cuenta_para_informe(p) for p in del_anio), "para el informe"),
                  _cifra(len(prods), "en total"), cls="grid grid-cols-3 gap-2 mt-3")
    extra_a = Div(_cifra(len(acts), f"en {anio}"),
                  _cifra(sum(a["ambito"] == "internacional" for a in acts), "internacionales"),
                  cls="grid grid-cols-3 gap-2 mt-3")
    return [
        _tarjeta("book-open", "Mis productos", "Artículos indexados o arbitrados, reportes de "
                 "investigación, libros y presentaciones.", 3, "/productos", extra_p),
        _tarjeta("calendar-days", "Mis actividades", "Seminarios, congresos, visitas y escuelas.",
                 3, "/actividades", extra_a),
    ]


def _tarjeta_perfil(uid):
    p = perfiles.obtener(uid)
    porcentaje, faltan = perfiles.completitud(p, len(perfiles.areas(uid)))
    extra = Div(Progress(value=str(porcentaje), cls="mt-3 mb-1"),
                P(f"{porcentaje} % completo" + (f" · falta: {', '.join(faltan[:3])}"
                                                 + ("…" if len(faltan) > 3 else "") if faltan else ""),
                  cls=TextPresets.muted_sm))
    return _tarjeta("user-round", "Mi perfil", "Datos básicos, ORCID, MathSciNet, zbMATH, áreas MSC "
                    "y foto.", 2, "/perfil", extra)


@rt("/")
def get(auth):
    tarjetas = []
    if auth["es_investigador"]:
        tarjetas += [*_tarjetas_produccion(auth["id"]), _tarjeta_perfil(auth["id"])]
    tarjetas.append(_tarjeta(*MODULO_DIRECTORIO))
    if auth["es_admin"]:
        tarjetas.append(_tarjeta(*MODULO_USUARIOS))
    if auth["es_investigador"]:
        tarjetas += [_tarjeta(*m) for m in MODULOS_FUTUROS]
    return pagina(
        "Inicio",
        Div(H2(f"Hola, {auth['nombres']}"),
            P("Los módulos marcados con su fase se habilitarán en las próximas entregas.",
              cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Grid(*tarjetas, cols_sm=1, cols_md=2, cols_lg=3, gap=4),
        usuario=auth, seccion="inicio")
