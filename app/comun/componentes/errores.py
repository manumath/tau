"""Páginas de error con el estilo del portal y avisos cuando falla una petición HTMX.

- Las rutas pueden seguir devolviendo `Response("…", status_code=403|404)`: el «after hook»
  `paginas_de_error` las convierte en una página completa si la petición no es de HTMX.
- Las rutas que no existen pasan por `no_encontrado` (manejador de 404 de la app).
- En peticiones HTMX, htmx ignora por defecto las respuestas 4xx/5xx (no pasa nada en pantalla);
  static/js/avisos.js muestra entonces un aviso rojo con un mensaje comprensible.
"""
from fasthtml.common import A, Div, FtResponse, JSONResponse, P, Response, Span
from monsterui.all import H2, ButtonT, UkIcon
from starlette.responses import FileResponse, StreamingResponse

from app.comun.componentes.layout import pagina

TEXTOS = {
    403: ("Sin permiso", "shield-alert", "No tiene permiso para ver esta página. Si cree que debería "
                                         "tenerlo, consulte a la administración del instituto."),
    404: ("No encontrado", "search-x", "La página no existe o el registro fue eliminado."),
    503: ("En mantenimiento", "wrench", "El sistema está en mantenimiento: por ahora solo se puede "
                                        "consultar. Intente el cambio más tarde."),
}
ERROR_INTERNO = ("Error del sistema", "triangle-alert", "Ocurrió un error inesperado y no se pudo completar la "
                 "operación. Intente de nuevo; si se repite, avise a la administración indicando el código de "
                 "referencia.")


def _usuario(req):
    """Usuario de la sesión (si la hay), para mostrar la navegación también en el error."""
    if req.scope.get("auth"):
        return req.scope["auth"]
    uid = req.session.get("uid") if "session" in req.scope else None
    if not uid:
        return None
    from app.comun import usuarios
    u = usuarios.con_perfil(uid)
    return u if u and u["activo"] and not u["debe_cambiar_pass"] else None


def pagina_error(req, codigo: int, referencia: str | None = None):
    titulo, icono, texto = ERROR_INTERNO if codigo == 500 else TEXTOS[codigo]
    try:
        usuario = _usuario(req)
    except Exception:  # si el error vino de la base, la página de error no debe fallar también
        usuario = None
    contenido = Div(
        Div(UkIcon(icono, height=48, width=48), cls="flex justify-center text-muted-foreground"),
        H2(titulo, cls="mt-4"),
        P(texto, cls="text-muted-foreground max-w-md mx-auto mt-2"),
        P("Código de referencia: ", Span(referencia, cls="font-mono font-semibold"), cls="text-sm mt-4")
        if referencia else "",
        A(UkIcon("arrow-left", height=14, width=14), "Volver al inicio" if usuario else "Ir al ingreso",
          href="/" if usuario else "/login", cls=f"uk-btn {ButtonT.default} inline-flex gap-1 mt-6"),
        cls="text-center py-16")
    return pagina(titulo, contenido, usuario=usuario)


def paginas_de_error(req, resp):
    """After hook: 403/404 en texto plano → página con estilo (solo peticiones normales)."""
    if (isinstance(resp, Response) and resp.status_code in TEXTOS
            and not isinstance(resp, (JSONResponse, FileResponse, StreamingResponse))
            and "hx-request" not in req.headers):
        return FtResponse(pagina_error(req, resp.status_code), status_code=resp.status_code)


def no_encontrado(req, exc):
    """Manejador de 404 para rutas inexistentes (y HTTPException(404))."""
    if "hx-request" in req.headers or req.url.path.startswith("/api/"):
        return Response("No encontrado", status_code=404)
    return pagina_error(req, 404)


def error_interno(req, exc):
    """Manejador de errores no controlados (500): página con el código de referencia que registró
    app/comun/registros.py; a HTMX, texto y la cabecera X-Referencia (static/js/avisos.js la muestra)."""
    referencia = req.scope.get("referencia") or "-"
    if "hx-request" in req.headers or req.url.path.startswith("/api/"):
        return Response(f"Error del sistema (referencia {referencia})", status_code=500,
                        headers={"X-Referencia": referencia})
    return FtResponse(pagina_error(req, 500, referencia), status_code=500)
