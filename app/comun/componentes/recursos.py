"""Scripts y hojas de estilo de las páginas, servidos por el propio portal (sin CDN).

Se sirven en /static (ver `montar`), fuera del control de sesión.

- static/vendor/: librerías de terceros con versión fija (htmx 2.0.7, fasthtml.js 1.0.12,
  Franken UI 2.0.0, KaTeX 0.16.21). Para actualizar una, reemplace sus archivos y la versión aquí.
- static/css/tailwind.css: las clases de Tailwind que usa el código, compiladas con
  scripts/estilos.sh (MonsterUI usaba el compilador de Tailwind en el navegador, desde un CDN).

Cada URL lleva `?v=<hash del archivo>`: al cambiar un archivo, el navegador no usa la copia vieja.
La política de seguridad de contenido (app/comun/cabeceras.py) solo admite recursos propios.
"""
import hashlib
from functools import cache

from fasthtml.common import Link, Meta, Script
from monsterui.core import scrollspy_style
from starlette.staticfiles import StaticFiles

from app.comun import config

VERSIONES = {"htmx": "2.0.7", "fasthtml-js": "1.0.12", "franken-ui": "2.0.0", "katex": "0.16.21",
             "tailwind": "3.4.17"}



CARPETA = config.RAIZ / "static"


class _Estaticos(StaticFiles):
    """Archivos de static/. Con ?v= (URL versionada por contenido) se pueden guardar un año."""

    def file_response(self, *args, **kwargs):
        respuesta = super().file_response(*args, **kwargs)
        scope = args[2] if len(args) > 2 else kwargs.get("scope")
        if scope and b"v=" in scope.get("query_string", b""):
            respuesta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return respuesta


def montar(app):
    """Sirve static/ en /static y quita la ruta estática genérica de FastHTML, que aceptaba
    cualquier URL terminada en .css, .js, .png… (y capturaba, p. ej., las terminadas en .xlsx)."""
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/{fname:path}.{ext:static}"]
    app.mount("/static", _Estaticos(directory=CARPETA), name="static")


@cache
def url(ruta: str) -> str:
    """'vendor/htmx/htmx.min.js' → '/static/vendor/htmx/htmx.min.js?v=<hash corto del contenido>'."""
    contenido = (CARPETA / ruta).read_bytes()
    return f"/static/{ruta}?v={hashlib.sha256(contenido).hexdigest()[:10]}"


def encabezados():
    """Lo que va en <head> de todas las páginas (antes lo armaban fast_app y MonsterUI)."""
    return [
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover"),
        Link(rel="icon", type="image/svg+xml", href=url("favicon.svg")),
        Script(src=url("vendor/htmx/htmx.min.js")),
        Script(src=url("vendor/fasthtml/fasthtml.js")),
        Link(rel="stylesheet", href=url("vendor/franken-ui/core.min.css")),
        Script(type="module", src=url("vendor/franken-ui/core.iife.js")),
        Link(rel="stylesheet", href=url("css/tailwind.css")),
        # Tema de Franken UI (azul; claro u oscuro según la elección guardada o, si no hay, el sistema):
        # el mismo código que headers_theme de MonsterUI, en un archivo (sin defer: antes de pintar).
        Script(src=url("js/tema-inicial.js")),
        scrollspy_style,
        Script(type="module", src=url("vendor/franken-ui/icon.iife.js")),
        Script(src=url("js/tema.js"), defer=True),  # selector de tema claro / oscuro / sistema
        Script(src=url("js/tablas.js"), defer=True),  # orden, filtro y CSV en <table data-tabla>
        Script(src=url("js/acciones.js"), defer=True),  # botones, selects y modal (data-accion…)
        Script(src=url("js/avisos.js"), defer=True),  # avisos emergentes y errores de HTMX
        Link(rel="stylesheet", href=url("vendor/katex/katex.min.css")),
        Script(type="module", src=url("js/katex.mjs")),  # fórmulas LaTeX
    ]
