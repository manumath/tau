"""Registros de actividad y de errores (PLAN.md §48, paso 3).

- `configurar()`: el registro «portal» escribe en la consola y, salvo `PORTAL_REGISTROS=consola`, también en
  `<directorio de la base>/registros/portal.log` (rota a los 10 MB y guarda 5 archivos).
- `RegistroPeticiones` (middleware ASGI): una línea por petición con método, ruta, código, duración y el id de
  quien la hizo. Por privacidad no registra la consulta (`?q=…` puede traer nombres) ni el cuerpo, y oculta
  los tokens de `/recuperar/…` y `/acceso/…`. Las de más de `LENTA_MS` van como WARNING. No registra `/static` ni `/salud`.
- Un error no controlado se registra con su traza y un **código de referencia** corto, que la página de
  error muestra a quien lo sufrió (y el aviso de htmx, por la cabecera X-Referencia): así la administración
  encuentra la traza en el registro. Con `PORTAL_AVISO_ERRORES=correo@…`, además se avisa por correo (a lo
  más uno cada `AVISO_CADA_S` segundos).
"""
import logging
import re
import secrets
import time
import traceback
from logging.handlers import RotatingFileHandler

from app.comun import config

log = logging.getLogger("portal")
log_peticiones = logging.getLogger("portal.peticiones")
LENTA_MS = 1000
AVISO_CADA_S = 15 * 60
_SIN_REGISTRO = re.compile(r"/static/.*|/salud|/favicon\.ico")
_TOKENS = re.compile(r"^(/(?:recuperar|acceso)/)[^/]+")
_ultimo_aviso = 0.0


def configurar():
    """Idempotente: se llama al crear la app (también en cada prueba)."""
    if getattr(log, "_configurado", False):
        return
    log.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    log.addHandler(consola)
    if config.REGISTROS != "consola":
        carpeta = config.DB_PATH.parent / "registros"
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = RotatingFileHandler(carpeta / "portal.log", maxBytes=10 * 1024 * 1024, backupCount=5,
                                      encoding="utf-8")
        archivo.setFormatter(formato)
        log.addHandler(archivo)
    log.propagate = False
    log._configurado = True


def ruta_registrable(ruta: str) -> str:
    """La ruta sin datos sensibles: los tokens de recuperación e invitación se ocultan."""
    return _TOKENS.sub(r"\1…", ruta)


def _usuario(scope) -> str:
    auth = scope.get("auth")
    return str(auth["id"]) if isinstance(auth, dict) and auth.get("id") else "-"


def _avisar(referencia: str, ruta: str, usuario: str, traza: str):
    """Correo a la administración, si está configurado y no se avisó hace poco."""
    global _ultimo_aviso
    if not config.AVISO_ERRORES or time.monotonic() - _ultimo_aviso < AVISO_CADA_S:
        return
    _ultimo_aviso = time.monotonic()
    from app.comun import correo
    try:
        correo.enviar(config.AVISO_ERRORES, f"{config.NOMBRE_SISTEMA}: error en el servidor ({referencia})",
                      f"Ocurrió un error no controlado.\n\nReferencia: {referencia}\nRuta: {ruta}\nUsuario: {usuario}\n\n"
                      f"{traza}\nLos siguientes errores de los próximos {AVISO_CADA_S // 60} minutos solo quedan en "
                      "el registro.")
    except Exception:  # el aviso nunca debe ocultar el error original
        log.exception("No se pudo enviar el aviso de error por correo")


class RegistroPeticiones:
    """Middleware ASGI de registro de peticiones y errores."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or _SIN_REGISTRO.fullmatch(scope["path"]):
            return await self.app(scope, receive, send)
        inicio, estado = time.perf_counter(), {"codigo": 500}

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                estado["codigo"] = mensaje["status"]
            await send(mensaje)

        ruta = ruta_registrable(scope["path"])
        try:
            await self.app(scope, receive, enviar)
        except Exception:
            referencia = secrets.token_hex(3)
            scope["referencia"] = referencia  # la lee la página de error (mismo scope)
            traza = traceback.format_exc()
            log.error("Error %s en %s %s (usuario %s)\n%s", referencia, scope["method"], ruta, _usuario(scope),
                      traza.rstrip())
            _avisar(referencia, f"{scope['method']} {ruta}", _usuario(scope), traza)
            raise
        finally:
            ms = round(1000 * (time.perf_counter() - inicio))
            nivel = logging.WARNING if ms >= LENTA_MS else logging.INFO
            log_peticiones.log(nivel, "%s %s %s %d ms usuario=%s%s", scope["method"], ruta, estado["codigo"], ms,
                               _usuario(scope), " (lenta)" if nivel == logging.WARNING else "")
