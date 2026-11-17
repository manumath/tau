"""Marco de las páginas públicas (sin sesión): cabecera con la marca y los enlaces a lo que esta instalación publica, y pie.
Lo usan el directorio de investigadores, los indicadores públicos y la página de privacidad (PLAN §55, §62 y §73)."""
from fasthtml.common import A, Div, Footer, Header, Main, P, Span, Title
from monsterui.all import Container, ContainerT, TextPresets

from app.comun import config, modulos
from app.comun.componentes.layout import con_h1, isotipo

# Secciones públicas, en su orden: solo se enlazan las de los módulos activos.
SECCIONES = (("Investigadores", "/publico/investigadores"), ("Indicadores", "/publico/indicadores"),
             ("Privacidad", "/publico/privacidad"))


def secciones_activas() -> list[tuple[str, str]]:
    return [(texto, href) for texto, href in SECCIONES if modulos.direccion_activa(href)]


def pagina_publica(titulo, *contenido, pie: str | None = None):
    contenido = con_h1(contenido, titulo)
    secciones = secciones_activas()
    cabecera = Header(Container(Div(
        # Marca de la Carrera y nombre del sistema, como en el resto (PLAN §55 y §62; decisión del 8-nov-2026).
        A(Div(*isotipo(), Span(config.NOMBRE_SISTEMA, cls="font-marca text-lg font-bold tracking-wide"),
              Span(config.NOMBRE_CARRERA, cls="hidden sm:inline text-sm text-muted-foreground"),
              cls="flex items-center gap-2"), href=secciones[0][1], aria_label=config.NOMBRE_COMPLETO,
          cls="min-w-0"),
        Div(*[A(texto, href=href, cls="text-sm hover:underline") for texto, href in secciones],
            A("Ingresar", href="/login", cls="uk-btn uk-btn-default uk-btn-sm"),
            cls="flex items-center gap-4"),
        cls="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-3"), cls=ContainerT.xl),
        cls="border-b border-border")
    pie = Footer(Container(P(pie or f"{config.NOMBRE_CARRERA} y su {config.NOMBRE_INSTITUTO} · Información publicada "
                                    "por cada investigador(a).",
                             cls=(TextPresets.muted_sm, "py-6")), cls=ContainerT.xl),
                 cls="border-t border-border mt-12")
    return (Title(f"{titulo} · {config.NOMBRE_SISTEMA}"), cabecera,
            Main(Container(*contenido, cls=(ContainerT.xl, "py-8"))), pie)
