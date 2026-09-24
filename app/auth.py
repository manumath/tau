"""Autenticación: Beforeware de sesión, login, logout y cambio de contraseña."""
from fasthtml.common import APIRouter, Beforeware, Div, P, Redirect, Response
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, Form, LabelInput, TextPresets, UkIcon)

from app import config, usuarios
from app.components.layout import mensaje_error, pagina
from app.db import auditar
from app.seguridad import errores_password, verificar_password

# Rutas accesibles sin sesión.
# Ojo: los patrones deben ser estrictos. Uno como r".*\.png" dejaría pasar sin sesión
# cualquier ruta que termine en .png.
RUTAS_PUBLICAS = [r"/login", r"/favicon\.ico", r"/[\w\-]+\.(css|js|png|svg|ico|woff2?)"]
# Rutas permitidas mientras la contraseña es temporal.
RUTAS_CAMBIO_PASS = {"/cambiar-password", "/logout"}


def _cargar_usuario(req, sess):
    """Carga el usuario de la sesión en `req.scope['auth']` o redirige al login.

    Se consulta la BD en cada petición para que desactivar una cuenta tenga efecto inmediato.
    """
    uid = sess.get("uid")
    usuario = usuarios.con_perfil(uid) if uid else None
    if not usuario or not usuario["activo"]:
        sess.clear()
        return Redirect("/login")
    req.scope["auth"] = usuario
    ruta = req.url.path
    if usuario["debe_cambiar_pass"] and ruta not in RUTAS_CAMBIO_PASS:
        return Redirect("/cambiar-password")
    if ruta.startswith("/admin") and not usuario["es_admin"]:
        return Response("No autorizado", status_code=403)
    if ruta.startswith("/perfil") and not usuario["es_investigador"]:
        return Response("Esta cuenta no tiene perfil de investigador.", status_code=403)


beforeware = Beforeware(_cargar_usuario, skip=RUTAS_PUBLICAS)

rt = APIRouter()


# --- Login -------------------------------------------------------------------

def form_login(email: str = "", error: str = ""):
    return Form(
        mensaje_error(error) if error else "",
        LabelInput("Correo institucional", id="email", type="email", value=email, required=True,
                   autocomplete="username", autofocus=not email),
        LabelInput("Contraseña", id="password", type="password", required=True,
                   autocomplete="current-password", autofocus=bool(email)),
        Button("Ingresar", cls=(ButtonT.primary, "w-full"), type="submit"),
        P("¿Olvidó su contraseña? Solicite una nueva a la administración del instituto.",
          cls=(TextPresets.muted_sm, "text-center")),
        method="post", action="/login", hx_post="/login", hx_swap="outerHTML",
        cls="space-y-4", id="form-login")


def _tarjeta_acceso(titulo, subtitulo, *contenido):
    return Card(
        Div(Div(UkIcon("sigma", height=40, width=40), cls="flex justify-center text-primary"),
            H2(titulo, cls="text-center text-xl"),
            P(subtitulo, cls=(TextPresets.muted_sm, "text-center")),
            cls="space-y-2 mb-6"),
        *contenido, cls="w-full max-w-md")


def _pagina_login(form):
    return pagina("Ingreso", _tarjeta_acceso("Portal de Investigación", config.NOMBRE_INSTITUTO,
                                             form))


@rt("/login")
def get(sess):
    if sess.get("uid"):
        return Redirect("/")
    return _pagina_login(form_login())


@rt("/login")
def post(req, sess, htmx, email: str = "", password: str = ""):
    email = (email or "").strip().lower()
    ip = req.client.host if req.client else None

    def fallo(msg):
        form = form_login(email, msg)
        return form if htmx.request else _pagina_login(form)

    if usuarios.bloqueado(email):
        return fallo(f"Demasiados intentos fallidos. Espere {config.LOGIN_VENTANA_MIN} minutos "
                     "o solicite a la administración que restablezca su contraseña.")
    usuario = usuarios.por_email(email)
    ok = verificar_password(usuario["pass_hash"] if usuario else None, password or "")
    if not ok or not usuario["activo"]:
        usuarios.registrar_intento(email, ip, False)
        return fallo("Correo o contraseña incorrectos.")

    usuarios.registrar_intento(email, ip, True)
    usuarios.registrar_acceso(usuario["id"])
    sess.clear()  # evita fijación de sesión
    sess["uid"] = usuario["id"]
    auditar(usuario["id"], "login", "usuario", usuario["id"])
    return Redirect("/cambiar-password" if usuario["debe_cambiar_pass"] else "/")


@rt("/logout")
def post(sess):
    sess.clear()
    return Redirect("/login")


# --- Cambio de contraseña ----------------------------------------------------

def form_password(errores=(), forzado=False):
    return Form(
        mensaje_error(*errores),
        LabelInput("Contraseña actual" + (" (la temporal que recibió)" if forzado else ""),
                   id="actual", type="password", required=True, autocomplete="current-password"),
        LabelInput("Nueva contraseña", id="nueva", type="password", required=True,
                   minlength=config.PASS_MIN_LARGO, autocomplete="new-password"),
        LabelInput("Repita la nueva contraseña", id="confirmacion", type="password",
                   required=True, autocomplete="new-password"),
        P(f"Mínimo {config.PASS_MIN_LARGO} caracteres, combinando letras con números o símbolos.",
          cls=TextPresets.muted_sm),
        Button("Guardar contraseña", cls=(ButtonT.primary, "w-full"), type="submit"),
        method="post", action="/cambiar-password", hx_post="/cambiar-password",
        hx_swap="outerHTML", cls="space-y-4", id="form-password")


def _pagina_password(auth, form):
    forzado = bool(auth["debe_cambiar_pass"])
    if forzado:
        # Sin navegación: hasta cambiarla, el usuario no puede usar el resto del portal.
        return pagina("Cambiar contraseña", _tarjeta_acceso(
            "Defina su contraseña",
            f"Hola, {auth['nombres']}. Por seguridad, reemplace la contraseña temporal "
            "antes de continuar.",
            form,
            Form(Button("Salir", cls=(ButtonT.ghost, "w-full mt-2"), type="submit"),
                 method="post", action="/logout")))
    return pagina("Cambiar contraseña",
                  Div(_tarjeta_acceso("Cambiar contraseña", auth["email"], form),
                      cls="flex justify-center"),
                  usuario=auth, seccion="password")


@rt("/cambiar-password")
def get(auth):
    return _pagina_password(auth, form_password(forzado=bool(auth["debe_cambiar_pass"])))


@rt("/cambiar-password")
def post(auth, sess, htmx, actual: str = "", nueva: str = "", confirmacion: str = ""):
    forzado = bool(auth["debe_cambiar_pass"])
    usuario = usuarios.por_id(auth["id"])
    errores = []
    if not verificar_password(usuario["pass_hash"], actual or ""):
        errores.append("La contraseña actual no es correcta.")
    errores += errores_password(nueva or "", confirmacion or "", usuario["email"], actual or "")
    if errores:
        form = form_password(errores, forzado)
        return form if htmx.request else _pagina_password(auth, form)

    usuarios.cambiar_password(auth["id"], nueva, temporal=False)
    auditar(auth["id"], "cambio_password", "usuario", auth["id"])
    add_toast(sess, "Contraseña actualizada.", "success")
    return Redirect("/")
