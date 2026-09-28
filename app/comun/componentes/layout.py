"""Estructura común de las páginas: barra de navegación, contenedor y modal."""
import fasthtml.common as fh
from fasthtml.common import A, Div, Form, Main, Span, Title
from monsterui.all import (H3, Button, ButtonT, Container, ContainerT, DivHStacked, NavBar,
                           TextPresets, UkIcon)

from app.comun import config, permisos

ID_MODAL = "modal"


def _enlace(texto, href, icono, activo=False, extra=""):
    cls = "flex items-center gap-1 " + ("font-semibold text-primary" if activo else "")
    return A(UkIcon(icono, height=16, width=16), texto, extra, href=href, cls=cls)


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
    if usuario["es_investigador"]:
        opciones.append(A(UkIcon("user-round", height=16, width=16), "Mi perfil", href="/perfil",
                          cls=item))
    if not usuario["es_investigador"]:
        opciones.append(A(UkIcon("id-card", height=16, width=16), "Mis datos personales", href="/mis-datos",
                          cls=item))
    if permisos.puede(usuario, "ver_auditoria"):
        opciones.append(A(UkIcon("scroll-text", height=16, width=16), "Auditoría", href="/admin/auditoria",
                          cls=item))
    if permisos.puede(usuario, "gestionar_catalogos"):
        opciones.append(A(UkIcon("library", height=16, width=16), "Catálogo de revistas", href="/admin/revistas",
                          cls=item))
        opciones.append(A(UkIcon("route", height=16, width=16), "Líneas de investigación", href="/admin/lineas",
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


def barra_navegacion(usuario: dict, seccion: str = ""):
    enlaces = [_enlace("Inicio", "/", "home", seccion == "inicio")]
    if usuario["es_investigador"]:
        enlaces += [_enlace("Actividades", "/actividades", "calendar-days", seccion == "actividades"),
                    _enlace("Productos", "/productos", "book-open", seccion == "productos")]
    if usuario["es_investigador"] or permisos.puede(usuario, "ver_todos_los_proyectos"):
        # Contador de propuestas por revisar: se carga aparte y se refresca solo (ver
        # /proyectos/pendientes/contador), para no consultar la BD en cada página.
        contador = Span(id="badge-pendientes", cls="hidden", hx_get="/proyectos/pendientes/contador",
                        hx_trigger="load", hx_swap="outerHTML")
        enlaces.append(_enlace("Proyectos", "/proyectos", "folder-kanban", seccion == "proyectos",
                               extra=contador))
    enlaces.append(_enlace("Investigadores", "/investigadores", "book-user",
                           seccion == "investigadores"))
    enlaces.append(_enlace("Docencia", "/docencia/planes", "graduation-cap", seccion == "docencia"))
    if (usuario["es_investigador"] or permisos.puede(usuario, "ver_informes_institucionales")
            or permisos.puede(usuario, "ver_cv_ajeno")):
        enlaces.append(_enlace("Informes", "/informes", "file-text", seccion == "informes"))
    if permisos.puede(usuario, "decidir_propuestas"):
        contador = Span(id="badge-propuestas", cls="hidden", hx_get="/admin/propuestas/contador",
                        hx_trigger="load", hx_swap="outerHTML")
        enlaces.append(_enlace("Propuestas", "/admin/propuestas", "landmark", seccion == "propuestas",
                               extra=contador))
    if permisos.puede(usuario, "ver_usuarios"):
        enlaces.append(_enlace("Usuarios", "/admin/usuarios", "users", seccion == "usuarios"))
    enlaces.append(_menu_usuario(usuario))
    marca = A(DivHStacked(Span("τ", cls="font-serif italic text-3xl leading-none text-primary", aria_hidden="true"),
                          H3(config.NOMBRE_SISTEMA, cls="text-lg tracking-wide")),
              href="/", title=config.DESCRIPCION_SISTEMA, aria_label=config.NOMBRE_COMPLETO)
    return NavBar(*enlaces, brand=marca, sticky=True, cls="px-6 py-3 border-b border-border")


def pagina(titulo: str, *contenido, usuario: dict | None = None, seccion: str = ""):
    """Página completa. Con usuario muestra la navegación; sin él, un lienzo centrado."""
    cuerpo = Container(*contenido, cls=(ContainerT.xl, "py-8")) if usuario else Div(
        *contenido, cls="min-h-screen flex items-center justify-center p-4 bg-muted/40")
    aviso = Div(UkIcon("wrench", height=16, width=16, cls="shrink-0"),
                Span("El sistema está en mantenimiento: puede consultar, pero por ahora los cambios no se guardan."),
                cls="flex items-center justify-center gap-2 px-4 py-2 text-sm bg-amber-100 text-amber-900 "
                    "dark:bg-amber-950 dark:text-amber-200 no-imprimir", role="status") \
        if config.SOLO_LECTURA else ""
    return (Title(f"{titulo} · {config.NOMBRE_SISTEMA}"),
            aviso,
            barra_navegacion(usuario, seccion) if usuario else "",
            Main(cuerpo),
            Div(id=ID_MODAL))


# --- Modal ligero sin dependencias JS: el servidor lo inserta en #modal y
# cerrarlo es vaciar ese contenedor. -----------------------------------------

JS_CERRAR = f"document.getElementById('{ID_MODAL}').innerHTML=''"


def modal(titulo: str, *contenido, ancho="max-w-lg"):
    return Div(
        Div(
            Div(H3(titulo, cls="text-lg"),
                Button(UkIcon("x"), cls=ButtonT.ghost, onclick=JS_CERRAR, aria_label="Cerrar",
                       type="button"),
                cls="flex items-center justify-between mb-4"),
            *contenido,
            cls=f"bg-background rounded-lg shadow-xl w-full {ancho} p-6 max-h-[90vh] overflow-y-auto",
            role="dialog", aria_modal="true", onclick="event.stopPropagation()"),
        cls="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4",
        onclick=JS_CERRAR,
        hx_on_keydown=f"if(event.key==='Escape'){{{JS_CERRAR}}}", tabindex="-1",
        # Foco al abrir para que Escape funcione sin clic previo.
        hx_on_htmx_load="this.focus()")


def cerrar_modal():
    """Fragmento OOB que vacía el modal."""
    return Div(id=ID_MODAL, hx_swap_oob="true")


def mensaje_error(*errores):
    if not errores:
        return ""
    return Div(*[Div(UkIcon("circle-alert", height=16, width=16, cls="shrink-0"), Span(e),
                     cls="flex gap-2 items-start") for e in errores],
               cls="rounded-md border border-red-300 bg-red-50 text-red-800 "
                   "dark:bg-red-950 dark:text-red-200 dark:border-red-800 p-3 text-sm space-y-1",
               role="alert")
