"""Cabeceras de seguridad de todas las respuestas, incluidos los archivos de /static.

La política de contenido (CSP) solo admite recursos del propio portal: ningún script, estilo,
fuente ni imagen de otros sitios, ninguna conexión a otros sitios desde la página, y el portal no
se puede incrustar en otra página.

Limitación conocida: `script-src` admite 'unsafe-inline' y 'unsafe-eval'. Las páginas tienen
manejadores en el HTML (onclick=…, hx-on…: unos 50) y scripts en línea (tema, avisos, KaTeX), y
htmx evalúa los hx-on con `Function`. Quitarlos permitiría una política estricta con nonces (ver
PLAN.md, sección 22, fase 1).
"""
from app.comun import config

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",   # íconos SVG en data: de Franken UI
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

CABECERAS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "x-frame-options": "DENY",  # para navegadores que no entienden frame-ancestors
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
}


class CabecerasSeguridad:
    """Middleware ASGI: agrega las cabeceras si la respuesta no las trae ya."""

    def __init__(self, app):
        self.app = app
        self.cabeceras = dict(CABECERAS)
        if config.HTTPS_ONLY:
            self.cabeceras["strict-transport-security"] = "max-age=31536000"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                presentes = {k.lower() for k, _ in mensaje.get("headers", [])}
                extra = [(k.encode(), v.encode()) for k, v in self.cabeceras.items() if k.encode() not in presentes]
                mensaje = {**mensaje, "headers": [*mensaje.get("headers", []), *extra]}
            await send(mensaje)

        await self.app(scope, receive, enviar)
