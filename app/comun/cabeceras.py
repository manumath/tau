"""Cabeceras de seguridad de todas las respuestas, incluidos los archivos de /static.

La política de contenido (CSP) solo admite recursos del propio portal: ningún script, estilo,
fuente ni imagen de otros sitios, ninguna conexión a otros sitios desde la página, y el portal no
se puede incrustar en otra página.

Política estricta para los scripts: solo archivos propios ('self'); ni código en línea ni `eval`.
Por eso el HTML no lleva manejadores (onclick, hx-on) ni <script> en línea: los comportamientos están en
static/js/acciones.js (atributos data-*), los avisos en static/js/avisos.js, el tema inicial en
static/js/tema-inicial.js y KaTeX en static/js/katex.mjs; htmx corre con allowEval=false.
tests/test_csp.py lo vigila. Los estilos sí admiten 'unsafe-inline' (atributos style= de Franken UI,
htmx y los gráficos SVG); no ejecutan código.
"""
from app.comun import config

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
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


class LimiteCuerpo:
    """Middleware ASGI: rechaza con 413 una petición cuyo cuerpo pasa de `maximo` bytes (PLAN §62, etapa 9).

    El adjunto más grande que acepta el sistema es de 20 MB (`adjuntos.MAX_BYTES`); sin este límite, una subida enorme
    llenaba el disco temporal antes de que la ruta la rechazara. Mira Content-Length y, si no viene (envío por
    partes), cuenta lo recibido."""

    def __init__(self, app, maximo: int):
        self.app = app
        self.maximo = maximo

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        largo = dict(scope.get("headers", [])).get(b"content-length")
        if largo and largo.isdigit() and int(largo) > self.maximo:
            return await self._demasiado_grande(send)
        recibido = 0

        async def recibir():
            nonlocal recibido
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibido += len(mensaje.get("body", b""))
                if recibido > self.maximo:
                    raise CuerpoDemasiadoGrande
            return mensaje

        try:
            await self.app(scope, recibir, send)
        except CuerpoDemasiadoGrande:
            await self._demasiado_grande(send)

    async def _demasiado_grande(self, send):
        texto = f"El envío supera el máximo de {self.maximo // (1024 * 1024)} MB.".encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(texto)).encode())]})
        await send({"type": "http.response.body", "body": texto})


class CuerpoDemasiadoGrande(Exception):
    pass
