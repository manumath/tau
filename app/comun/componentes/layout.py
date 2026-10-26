"""Estructura común de las páginas: menú lateral, barra superior, pestañas del teléfono, contenedor y modal."""
import unicodedata

import fasthtml.common as fh
from fasthtml.common import A, Div, Form, Img, Input, Li, Main, Span, Title, Ul
from monsterui.all import H3, Button, ButtonT, Container, ContainerT, TextPresets, UkIcon

from app.comun import config
from app.comun.componentes import recursos

ID_MODAL = "modal"


def selector_tema():
    """Claro, oscuro o el del sistema (static/js/tema.js guarda la elección en el navegador)."""
    def opcion(valor, icono, texto):
        return fh.Button(UkIcon(icono, height=14, width=14), texto, type="button", data_tema=valor,
                         aria_pressed="false",
                         cls="inline-flex items-center justify-center gap-1 rounded px-1 py-1 text-xs "
                             "hover:bg-muted")
    return Div(Span("Tema", cls="text-xs text-muted-foreground px-1"),
               Div(opcion("light", "sun", "Claro"), opcion("dark", "moon", "Oscuro"),
                   opcion("sistema", "monitor", "Sistema"),
                   cls="grid grid-cols-3 gap-0.5 rounded-md border border-border p-0.5", role="group",
                   aria_label="Tema"),
               cls="px-2 py-2 space-y-1 border-t border-border mt-1")


def _menu_usuario(usuario: dict):
    """Nombre del usuario con un desplegable: perfil, contraseña y salir."""
    item = "flex items-center gap-2 px-3 py-2 rounded hover:bg-muted w-full text-left text-sm"
    opciones = []
    if usuario.get("solo_estudiante"):          # solo ve su seguimiento: sin perfil, datos personales ni contraseña
        return Div(
            Button(Span(usuario["nombres"], cls="max-w-40 truncate"),
                   UkIcon("chevron-down", height=14, width=14), cls=(ButtonT.ghost, "gap-1"),
                   type="button", aria_haspopup="true"),
            Div(Div(Span(usuario["email"], cls=(TextPresets.muted_sm, "block px-3 py-2 truncate")), selector_tema(),
                    Form(fh.Button(UkIcon("log-out", height=16, width=16), "Salir", type="submit", cls=item),
                         method="post", action="/logout", hx_post="/logout"), cls="flex flex-col"),
                uk_dropdown="mode: click; pos: bottom-right", cls="uk-drop uk-dropdown w-60 p-1"))
    if usuario["es_investigador"]:
        opciones.append(A(UkIcon("user-round", height=16, width=16), "Mi perfil", href="/perfil",
                          cls=item))
    if not usuario["es_investigador"]:
        opciones.append(A(UkIcon("id-card", height=16, width=16), "Mis datos personales", href="/mis-datos",
                          cls=item))
    opciones += [
        A(UkIcon("key-round", height=16, width=16), "Cambiar contraseña", href="/cambiar-password",
          cls=item),
        selector_tema(),
        Form(fh.Button(UkIcon("log-out", height=16, width=16), "Salir", type="submit", cls=item),
             method="post", action="/logout", hx_post="/logout"),
    ]
    return Div(
        Button(Span(usuario["nombres"], cls="max-w-40 truncate"),
               UkIcon("chevron-down", height=14, width=14), cls=(ButtonT.ghost, "gap-1"),
               type="button", aria_haspopup="true"),
        Div(Div(Span(usuario["email"], cls=(TextPresets.muted_sm, "block px-3 py-2 truncate")),
                *opciones, cls="flex flex-col"),
            uk_dropdown="mode: click; pos: bottom-right", cls="uk-drop uk-dropdown w-60 p-1"))


def campo_busqueda(q: str = "", sugerencias: bool = True):
    """Búsqueda global (app/busqueda.py). Con `sugerencias`, despliega resultados mientras se escribe; Enter
    abre /buscar. La tecla «/» lleva a él y Escape cierra las sugerencias (static/js/acciones.js)."""
    extra = dict(hx_get="/buscar/sugerencias", hx_trigger="input changed delay:250ms", hx_target="#sugerencias-busqueda",
                 data_escape_vaciar="sugerencias-busqueda", id="busqueda-global") if sugerencias else {}
    return Form(Input(type="search", name="q", value=q, placeholder="Buscar…  /" if sugerencias else "Buscar",
                      autocomplete="off", aria_label="Buscar en el sistema", cls="uk-input h-9 w-full", **extra),
                Div(id="sugerencias-busqueda", data_cerrar_fuera=True) if sugerencias else "",
                action="/buscar", method="get", role="search", cls="relative")


# --- Navegación (PLAN.md §53) ----------------------------------------------------------------------------
# Pantallas grandes: menú lateral fijo y agrupado, que se pliega a solo íconos (la elección se recuerda en el
# navegador: static/js/disposicion-inicial.js la aplica antes de pintar). Teléfono: barra de pestañas abajo y
# «Más», que abre el mismo menú lateral como panel. Arriba, una franja con la búsqueda, la campana y el menú
# del usuario: cada pieza con id (contadores, campana) existe una sola vez en la página. Qué ve cada persona
# lo decide app/navegacion.py (`comun` no importa de los otros paquetes): main.py fija MENU y MENU_MOVIL.
# static/js/acciones.js marca el enlace de la página actual (aria-current) y abre, cierra y pliega el menú.

MENU = lambda usuario: []        # noqa: E731  usuario → [(título del grupo o None, [ítems])]
MENU_MOVIL = lambda usuario: []  # noqa: E731  usuario → ítems de la barra de abajo


def _version_clara_y_oscura(archivo: str, extension: str, alt: str, cls: str):
    """La marca a color en el tema claro y en blanco en el oscuro, como pide el manual de la Carrera (PLAN.md §55):
    las dos imágenes van en la página y el tema muestra una (la oculta no se anuncia)."""
    return (Img(src=recursos.url(f"img/marca/{archivo}.{extension}"), alt=alt, cls=f"{cls} dark:hidden"),
            Img(src=recursos.url(f"img/marca/{archivo}-blanco.{extension}"), alt=alt, cls=f"{cls} hidden dark:block"))


def isotipo(cls: str = "size-7"):
    """El nudo de la Carrera, sin texto (decorativo: el enlace que lo contiene lleva el nombre)."""
    return _version_clara_y_oscura("isotipo", "svg", "", f"shrink-0 {cls}")


def logotipo(cls: str = "w-60"):
    """Marca horizontal «Carrera de Matemática» (el manual pide al menos 100 px de ancho en pantalla)."""
    return _version_clara_y_oscura("logotipo", "png", config.NOMBRE_CARRERA, f"h-auto {cls}")


def _marca(usuario):
    return A(*isotipo(),
             Span(config.NOMBRE_SISTEMA, cls="lateral-texto font-marca text-lg font-bold tracking-wide"),
             href="/estudiante" if usuario.get("solo_estudiante") else "/", title=config.DESCRIPCION_SISTEMA,
             aria_label=config.NOMBRE_COMPLETO, cls="flex items-center gap-2 min-w-0")


def _enlace_menu(item):
    return Li(A(UkIcon(item["icono"], height=18, width=18, cls="shrink-0"),
                Span(item["texto"], cls="lateral-texto truncate"), item["insignia"] or "",
                href=item["href"], title=item["texto"], data_nav=True,
                cls="enlace-menu flex items-center gap-3 rounded-md px-3 py-2 text-sm text-foreground/80 "
                    "hover:bg-muted hover:text-foreground"))


def _clave_grupo(titulo: str) -> str:
    """'Acreditación' → 'acreditacion' (la usan estilos/entrada.css y static/js/disposicion-inicial.js)."""
    return unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()


def _grupo_menu(titulo, items):
    """Grupo del menú; con título, se pliega con su encabezado (PLAN.md §54) y el navegador lo recuerda."""
    lista = Ul(*[_enlace_menu(i) for i in items], cls="space-y-0.5")
    if not titulo:
        return Div(lista)
    clave = _clave_grupo(titulo)
    return Div(fh.Button(Span(titulo), UkIcon("chevron-down", height=14, width=14, cls="flecha-grupo"),
                         type="button", data_accion="plegar-grupo", aria_expanded="true",
                         cls="lateral-grupo grupo-plegable flex w-full items-center justify-between rounded px-3 pt-4 "
                             "pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground "
                             "hover:text-foreground"),
               lista, data_grupo=clave, cls="menu-grupo")


def menu_lateral(usuario: dict):
    grupos = [_grupo_menu(titulo, items) for titulo, items in MENU(usuario)]
    plegar = fh.Button(UkIcon("panel-left-close", height=18, width=18, cls="icono-plegar"),
                       UkIcon("panel-left-open", height=18, width=18, cls="icono-desplegar"),
                       type="button", data_accion="plegar-lateral", aria_label="Plegar o desplegar el menú",
                       title="Plegar o desplegar el menú",
                       cls="hidden lg:inline-flex rounded p-1.5 text-muted-foreground hover:bg-muted")
    cerrar = fh.Button(UkIcon("x", height=18, width=18), type="button", data_accion="cerrar-menu",
                       aria_label="Cerrar el menú", cls="lg:hidden rounded p-1.5 hover:bg-muted")
    return fh.Nav(Div(_marca(usuario), plegar, cerrar, cls="lateral-cabecera flex items-center justify-between "
                                                         "gap-2 px-4 h-14 border-b border-border shrink-0"),
                  Div(*grupos, cls="flex-1 overflow-y-auto px-2 py-2"),
                  id="menu-lateral", aria_label="Menú principal", cls="lateral no-imprimir")


def barra_superior(usuario: dict):
    """Franja de arriba: menú (teléfono), búsqueda, campana y usuario."""
    menu = fh.Button(UkIcon("menu", height=20, width=20), type="button", data_accion="abrir-menu",
                     aria_label="Abrir el menú", aria_controls="menu-lateral",
                     cls="lg:hidden rounded p-2 -ml-2 hover:bg-muted")
    estudiante = usuario.get("solo_estudiante")
    busqueda = "" if estudiante else (
        Div(campo_busqueda(), cls="hidden sm:block flex-1 max-w-xl"),
        A(UkIcon("search", height=20, width=20), href="/buscar", aria_label="Buscar", title="Buscar",
          cls="sm:hidden rounded p-2 hover:bg-muted"))
    return fh.Header(menu, Div(_marca(usuario), cls="lg:hidden"), *busqueda, Div(cls="flex-1 sm:hidden lg:hidden"),
                     Div(Span(id="campana-avisos", hx_get="/avisos/campana", hx_trigger="load", hx_swap="outerHTML"),
                         _menu_usuario(usuario), cls="ml-auto flex items-center gap-1"),
                     cls="barra-superior no-imprimir sticky top-0 z-30 flex items-center gap-3 h-14 px-4 sm:px-6 "
                         "border-b border-border bg-background/95 backdrop-blur")


COLUMNAS = {1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3", 4: "grid-cols-4", 5: "grid-cols-5"}


def pestanas_movil(usuario: dict):
    """Barra de abajo en el teléfono: las secciones principales y «Más», que abre el menú lateral."""
    items = [A(UkIcon(i["icono"], height=20, width=20), Span(i["texto"], cls="truncate max-w-full"),
               href=i["href"], data_nav=True,
               cls="enlace-menu flex flex-col items-center justify-center gap-0.5 px-1 text-[11px] "
                   "text-muted-foreground") for i in MENU_MOVIL(usuario)]
    if not usuario.get("solo_estudiante"):
        items.append(fh.Button(UkIcon("ellipsis", height=20, width=20), Span("Más"), type="button",
                               data_accion="abrir-menu", aria_controls="menu-lateral",
                               cls="flex flex-col items-center justify-center gap-0.5 px-1 text-[11px] "
                                   "text-muted-foreground"))
    return fh.Nav(*items, aria_label="Secciones principales",
                  cls="pestanas-movil no-imprimir lg:hidden fixed inset-x-0 bottom-0 z-30 grid h-16 border-t "
                      "border-border bg-background " + COLUMNAS[len(items)])


def pagina(titulo: str, *contenido, usuario: dict | None = None, seccion: str = ""):
    """Página completa. Con usuario muestra la navegación; sin él, un lienzo centrado. `seccion` ya no
    decide el enlace activo (lo marca acciones.js según la dirección); se conserva por compatibilidad."""
    cuerpo = Container(*contenido, cls=(ContainerT.xl, "py-8")) if usuario else Div(
        *contenido, cls="min-h-screen flex items-center justify-center p-4 bg-muted/40")
    aviso = Div(UkIcon("wrench", height=16, width=16, cls="shrink-0"),
                Span("El sistema está en mantenimiento: puede consultar, pero por ahora los cambios no se guardan."),
                cls="flex items-center justify-center gap-2 px-4 py-2 text-sm bg-amber-100 text-amber-900 "
                    "dark:bg-amber-950 dark:text-amber-200 no-imprimir", role="status") \
        if config.SOLO_LECTURA else ""
    # «Saltar al contenido»: invisible hasta recibir el foco con Tab; evita recorrer toda la navegación.
    saltar = A("Saltar al contenido", href="#contenido",
               cls="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-md "
                   "focus:bg-background focus:px-4 focus:py-2 focus:shadow-lg focus:ring-2 focus:ring-primary") \
        if usuario else ""
    if not usuario:
        return (Title(f"{titulo} · {config.NOMBRE_SISTEMA}"), aviso,
                Main(cuerpo, id="contenido", tabindex="-1", cls="outline-none"), Div(id=ID_MODAL))
    return (Title(f"{titulo} · {config.NOMBRE_SISTEMA}"),
            saltar,
            menu_lateral(usuario),
            Div(data_accion="cerrar-menu", cls="fondo-menu no-imprimir", aria_hidden="true"),
            Div(aviso, barra_superior(usuario),
                Main(cuerpo, id="contenido", tabindex="-1", cls="outline-none"),
                cls="columna-contenido min-h-screen pb-16 lg:pb-0"),
            pestanas_movil(usuario),
            Div(id=ID_MODAL))


# --- Modal ligero: el servidor lo inserta en #modal y cerrarlo es vaciar ese contenedor. Los botones
# usan data-accion="cerrar-modal"; el fondo (data-fondo-modal) lo cierra con un clic fuera del cuadro o
# con Escape. static/js/acciones.js (sin JavaScript en el HTML por la CSP) además pone el foco en el primer
# campo al abrirlo, lo retiene dentro con Tab y lo devuelve al botón que lo abrió al cerrarlo. ------------

CERRAR = {"data_accion": "cerrar-modal"}   # atributos de un botón que cierra el modal


def modal(titulo: str, *contenido, ancho="max-w-lg"):
    return Div(
        Div(
            Div(H3(titulo, id="modal-titulo", cls="text-lg"),
                Button(UkIcon("x"), cls=ButtonT.ghost, aria_label="Cerrar", type="button", **CERRAR),
                cls="flex items-center justify-between mb-4"),
            *contenido,
            cls=f"bg-background rounded-lg shadow-xl w-full {ancho} p-6 max-h-[90vh] overflow-y-auto",
            role="dialog", aria_modal="true", aria_labelledby="modal-titulo", tabindex="-1"),
        cls="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4",
        data_fondo_modal=True, tabindex="-1")


def cerrar_modal():
    """Fragmento OOB que vacía el modal."""
    return Div(id=ID_MODAL, hx_swap_oob="true")


def boton_espera(*contenido, cls=ButtonT.default, **kwargs):
    """Botón para operaciones que tardan (consultas a OpenAlex, envíos con correo): mientras dura la
    petición HTMX queda deshabilitado y muestra un ícono girando (como LoaderButton de MonsterUI,
    que no admite clases en tupla). Si la petición la hace el formulario, póngale a este
    hx_disabled_elt="find button[type='submit']"."""
    kwargs.setdefault("hx_disabled_elt", "this")
    clases = cls if isinstance(cls, tuple) else (cls,)
    return Button(Span(*contenido, cls="inline-flex items-center gap-1 group-disabled:opacity-0"),
                  UkIcon("loader-circle", height=16, width=16,
                         cls="absolute group-disabled:animate-spin group-enabled:hidden"),
                  cls=(*clases, "relative group disabled:cursor-not-allowed"), **kwargs)


def mensaje_error(*errores):
    """Resumen de errores. Al llegar en una respuesta, static/js/acciones.js le pasa el foco (y el lector de
    pantalla lo anuncia: role=alert), para que no quede fuera de la vista en un formulario largo."""
    if not errores:
        return ""
    return Div(*[Div(UkIcon("circle-alert", height=16, width=16, cls="shrink-0"), Span(e),
                     cls="flex gap-2 items-start") for e in errores],
               cls="rounded-md border border-red-300 bg-red-50 text-red-800 "
                   "dark:bg-red-950 dark:text-red-200 dark:border-red-800 p-3 text-sm space-y-1 outline-none",
               role="alert", tabindex="-1", data_resumen_errores=True)
