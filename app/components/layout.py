"""Estructura común de las páginas: barra de navegación, contenedor y modal."""
from fasthtml.common import A, Div, Form, Main, Span, Title
from monsterui.all import (H3, Button, ButtonT, Container, ContainerT, DivHStacked, NavBar,
                           TextPresets, UkIcon)

from app import config

ID_MODAL = "modal"


def _enlace(texto, href, icono, activo=False):
    cls = "flex items-center gap-1 " + ("font-semibold text-primary" if activo else "")
    return A(UkIcon(icono, height=16, width=16), texto, href=href, cls=cls)


def barra_navegacion(usuario: dict, seccion: str = ""):
    enlaces = [_enlace("Inicio", "/", "home", seccion == "inicio")]
    if usuario["es_admin"]:
        enlaces.append(_enlace("Usuarios", "/admin/usuarios", "users", seccion == "usuarios"))
    enlaces += [
        _enlace("Contraseña", "/cambiar-password", "key-round", seccion == "password"),
        Span(f'{usuario["nombres"]} {usuario["apellidos"]}', cls=TextPresets.muted_sm),
        Form(Button(UkIcon("log-out", height=16, width=16), "Salir", cls=ButtonT.ghost,
                    type="submit"),
             method="post", action="/logout", hx_post="/logout"),
    ]
    marca = A(DivHStacked(UkIcon("sigma", height=26, width=26),
                          H3("Portal de Investigación", cls="text-lg")), href="/")
    return NavBar(*enlaces, brand=marca, sticky=True, cls="px-6 py-3 border-b border-border")


def pagina(titulo: str, *contenido, usuario: dict | None = None, seccion: str = ""):
    """Página completa. Con usuario muestra la navegación; sin él, un lienzo centrado."""
    cuerpo = Container(*contenido, cls=(ContainerT.xl, "py-8")) if usuario else Div(
        *contenido, cls="min-h-screen flex items-center justify-center p-4 bg-muted/40")
    return (Title(f"{titulo} · {config.NOMBRE_INSTITUTO}"),
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
