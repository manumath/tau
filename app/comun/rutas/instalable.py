"""Manifiesto web (PLAN §73, mejora 8): permite «instalar» el sistema en el teléfono o el escritorio, con su nombre y su
icono, y abrirlo sin las barras del navegador. No guarda nada fuera de línea: sin conexión no funciona. Es público (lo
pide el navegador antes de ingresar) y no dice nada que no esté ya en la página de ingreso."""
from fasthtml.common import APIRouter, JSONResponse, Response

from app.comun import config, marca
from app.comun.componentes import recursos

rt = APIRouter()
URL = "/manifest.webmanifest"
ICONOS = (192, 512)


@rt(URL)
def get():
    return JSONResponse({
        "name": config.NOMBRE_COMPLETO, "short_name": config.NOMBRE_SISTEMA, "lang": "es", "start_url": "/",
        "scope": "/", "display": "standalone", "background_color": "#ffffff", "theme_color": marca.PRINCIPAL,
        "icons": [{"src": recursos.url(f"img/marca/icono-{lado}.png"), "sizes": f"{lado}x{lado}", "type": "image/png",
                   "purpose": "any"} for lado in ICONOS]},
        media_type="application/manifest+json", headers={"Cache-Control": "public, max-age=3600"})


@rt("/tema.css")
def get():
    """Los colores de la marca de esta instalación (PLAN §74). Público: lo carga también la página de ingreso. La
    dirección lleva ?v=<hash>, así que se puede guardar un año."""
    return Response(marca.css_del_tema(), media_type="text/css; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})

