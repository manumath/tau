"""Inicio (PLAN.md §54): una sola bandeja de pendientes, con un subtítulo por rol (lo que requiere atención, con
enlace directo), y una fila de cifras con enlace. Los accesos a los módulos los da el menú lateral: el inicio no
los repite.

Cada módulo **aporta** sus pendientes y sus cifras (`inicio` y `cifras` en `app/<paquete>/aportes.py`, PLAN §73) y
aquí solo se juntan los de los módulos activos, por sección: este archivo no importa de ningún paquete. Un pendiente
o una cifra cuyo enlace lleva a un módulo apagado no se muestra o queda sin enlace."""
from fasthtml.common import A, APIRouter, Div, Li, P, Span, Ul
from monsterui.all import H2, H3, Card, TextPresets, UkIcon

from app.comun import formato, modulos, permisos, vinculos
from app.comun.componentes.layout import pagina

rt = APIRouter()

# Secciones de la bandeja, en su orden: clave → (icono, título). Los aportes nombran la sección por su clave.
SECCIONES = {"instalacion": ("rocket", "Primeros pasos"), "mio": ("list-checks", "Lo mío"), "carrera": ("graduation-cap", "Docencia"),
             "instituto": ("landmark", "Dirección del Instituto"), "estudiantes": ("users-round", "Estudiantes"),
             "fichas": ("id-card", "Fichas académicas"), "calidad_datos": ("list-checks", "Calidad de datos")}


def _cifra(valor, texto, href=None):
    contenido = (Span(formato.numero(valor) if isinstance(valor, float) else str(valor), cls="text-2xl font-semibold tabular-nums"), Span(texto, cls=TextPresets.muted_sm))
    cls = "flex flex-col rounded-lg border border-border px-4 py-3"
    activo = href and modulos.direccion_activa(href)
    return A(*contenido, href=href, cls=cls + " hover:bg-muted") if activo else Div(*contenido, cls=cls)


def _item(texto, href, tono="ambar", detalle=None):
    color = {"ambar": "text-amber-700 dark:text-amber-400", "rojo": "text-destructive", "info": "text-primary"}[tono]
    return Li(A(Div(UkIcon("circle-alert" if tono != "info" else "info", height=16, width=16, cls=f"shrink-0 mt-0.5 {color}"),
                    Div(Span(texto, cls="text-sm"),
                        P(detalle, cls=TextPresets.muted_sm) if detalle else "", cls="min-w-0"),
                    UkIcon("chevron-right", height=14, width=14, cls="ml-auto shrink-0 mt-0.5 text-muted-foreground"),
                    cls="flex items-start gap-2"),
                href=href, cls="block rounded px-2 py-2 hover:bg-muted"))


def _secciones(auth):
    """[(icono, título, ítems)] con lo que aportan los módulos activos, en el orden de SECCIONES."""
    aportados = [x for aporte in modulos.aportes("inicio") for x in aporte(auth)]
    aportados = [x for x in aportados if modulos.direccion_activa(x[2]["href"])]
    titulos = dict(SECCIONES)
    if permisos.puede(auth, "gestionar_vinculos", vinculos.carrera()):
        titulos["carrera"] = (SECCIONES["carrera"][0], "Dirección de Carrera")
    return [(*titulos[clave], [_item(**x) for _, _, x in sorted((a for a in aportados if a[0] == clave),
                                                                 key=lambda a: a[1])]) for clave in SECCIONES]


def _cifras(auth):
    grupos = sorted((g for aporte in modulos.aportes("cifras") for g in aporte(auth)), key=lambda g: g[0])
    return [(titulo, [_cifra(*c) for c in cifras]) for _, titulo, cifras in grupos]


def _bandeja(secciones):
    """Todos los pendientes en una tarjeta: un subtítulo por rol, o «Todo al día»."""
    con_algo = [(i, t, items) for i, t, items in secciones if items]
    if not con_algo:
        return Card(P(UkIcon("circle-check", height=18, width=18, cls="inline mr-2 text-green-700 dark:text-green-400"),
                      "Todo al día: no tiene pendientes.", cls="text-sm"))
    bloques = [Div(Div(UkIcon(icono, height=16, width=16, cls="text-primary"),
                       H3(titulo, cls="text-xs font-semibold uppercase tracking-wide text-muted-foreground"),
                       cls="flex items-center gap-2 px-2"),
                   Ul(*items, cls="mt-1"), cls="py-3 first:pt-0 last:pb-0")
               for icono, titulo, items in con_algo]
    return Card(Div(*bloques, cls="divide-y divide-border -mx-2"))


@rt("/")
def get(auth):
    return pagina(
        "Inicio",
        Div(H2(f"Hola, {auth['nombres']}"), P("Lo que requiere su atención.", cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Div(H3("Pendientes", cls="text-base font-semibold mb-3"), _bandeja(_secciones(auth)), cls="mb-8 max-w-3xl"),
        *[Div(H3(titulo, cls="text-base font-semibold mb-3"), Div(*tiles, cls="grid grid-cols-2 md:grid-cols-4 gap-3"),
              cls="mb-8 max-w-3xl") for titulo, tiles in _cifras(auth)],
        usuario=auth, seccion="inicio")
