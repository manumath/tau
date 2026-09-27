"""Autenticación: Beforeware de sesión, login, logout y cambio de contraseña."""
from fasthtml.common import A, APIRouter, Beforeware, Div, P, Redirect, Response
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, Form, LabelInput, TextPresets, UkIcon)

from app.comun import config, correo, tokens, usuarios
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.db import auditar
from app.comun.seguridad import errores_password, verificar_password

# Rutas accesibles sin sesión.
# Ojo: los patrones deben ser estrictos. Uno como r".*\.png" dejaría pasar sin sesión
# cualquier ruta que termine en .png.
# Los archivos estáticos (/static) no pasan por aquí: están montados aparte (componentes/recursos.py).
RUTAS_PUBLICAS = [r"/login", r"/favicon\.ico",
                  r"/recuperar", r"/recuperar/[\w\-]+",
                  r"/publico", r"/publico/.*", r"/api/v1/.*"]
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

# Rutas que modifican solo la sesión (y registros de acceso sin importancia en una mudanza).
PERMITIDAS_EN_SOLO_LECTURA = {"/login", "/logout"}


def _solo_lectura(req):
    """Con PORTAL_SOLO_LECTURA=1 rechaza toda petición que modifique datos (se usa al exportar los
    datos para una mudanza, para que nada cambie después de la copia)."""
    if (config.SOLO_LECTURA and req.method not in ("GET", "HEAD", "OPTIONS")
            and req.url.path not in PERMITIDAS_EN_SOLO_LECTURA):
        return Response("El portal está en mantenimiento: por ahora solo se puede consultar.",
                        status_code=503)


# Sin rutas excluidas: el modo solo lectura también protege las públicas (p. ej. /recuperar).
beforeware_solo_lectura = Beforeware(_solo_lectura)


# --- Protección CSRF ------------------------------------------------------------------------------
#
# La cookie de sesión es SameSite=Lax: el navegador no la envía en formularios de *otros sitios*.
# Pero otro subdominio del mismo dominio (p. ej. una página cualquiera en *.umsa.bo) es el «mismo
# sitio» y sí la recibiría. Por eso toda petición que modifica datos debe venir del propio portal,
# según Origin (o Referer, si falta). Es la verificación recomendada por OWASP; no requiere tokens.

METODOS_SEGUROS = ("GET", "HEAD", "OPTIONS")


def _netloc(url: str | None) -> str | None:
    from urllib.parse import urlsplit
    if not url or url == "null":
        return None
    partes = urlsplit(url)
    return partes.netloc.lower() if partes.scheme in ("http", "https") and partes.netloc else None


def origenes_permitidos(req) -> set[str]:
    """El propio portal: el host de la petición (lo fija el navegador, no la página que envía) y
    la dirección pública configurada (PORTAL_URL), más PORTAL_ORIGENES_EXTRA si hiciera falta."""
    permitidos = {req.url.netloc.lower()}
    for url in (config.URL_BASE, *config.ORIGENES_EXTRA):
        if (n := _netloc(url)):
            permitidos.add(n)
    return permitidos


def _origen_valido(req):
    if req.method in METODOS_SEGUROS:
        return None
    origen = req.headers.get("origin")
    if origen is not None:
        # «null» (iframes aislados, redirecciones entre sitios) tampoco se acepta.
        valido = _netloc(origen) in origenes_permitidos(req)
    elif (referer := req.headers.get("referer")):
        valido = _netloc(referer) in origenes_permitidos(req)
    else:
        # Sin Origin ni Referer no es un navegador enviando la cookie de otra persona (los
        # navegadores actuales envían Origin en todo POST); se admite (clientes, pruebas).
        valido = True
    if not valido:
        return Response("Solicitud rechazada: no proviene del portal.", status_code=403)
    return None


# Sin rutas excluidas: también protege el ingreso (evita que otro sitio inicie sesión por la víctima).
beforeware_origen = Beforeware(_origen_valido)

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
        P(A("¿Olvidó su contraseña?", href="/recuperar", cls="text-primary hover:underline"),
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


# --- Recuperar contraseña (y definirla desde una invitación) ----------------------------------------

def form_recuperar(email="", error=None):
    return Form(
        mensaje_error(error) if error else "",
        LabelInput("Correo institucional", id="email", type="email", value=email, required=True,
                   autocomplete="username", autofocus=True),
        Button("Enviar enlace", cls=(ButtonT.primary, "w-full"), type="submit"),
        P(A("Volver al ingreso", href="/login", cls="text-primary hover:underline"),
          cls=(TextPresets.muted_sm, "text-center")),
        method="post", action="/recuperar", hx_post="/recuperar", hx_swap="outerHTML",
        cls="space-y-4", id="form-recuperar")


@rt("/recuperar")
def get():
    return pagina("Recuperar contraseña", _tarjeta_acceso(
        "Recuperar contraseña", "Le enviaremos un enlace para definir una nueva.", form_recuperar()))


@rt("/recuperar")
def post(req, htmx, email: str = ""):
    email = email.strip().lower()
    u = usuarios.por_email(email) if email else None
    # Misma respuesta exista o no la cuenta: así no se puede averiguar quién está registrado.
    if u and u["activo"] and not tokens.demasiados_pedidos(u["id"]):
        enlace = f"{config.URL_BASE}/recuperar/{tokens.emitir(u['id'], 'recuperar')}"
        correo.enviar(u["email"], "Recuperar su contraseña del Portal de Investigación",
                      f"Hola, {u['nombres']}:\n\nPara definir una nueva contraseña, abra este enlace "
                      f"(vale una vez y durante una hora):\n\n{enlace}\n\n"
                      "Si no lo solicitó, ignore este mensaje: su contraseña actual sigue vigente.")
        auditar(u["id"], "solicitar_recuperacion", "usuario", u["id"], req.client.host if req.client else None)
    listo = Div(P("Si el correo corresponde a una cuenta activa, le enviamos un enlace para definir una "
                  "nueva contraseña. Revise su bandeja de entrada (y la de spam).", cls="text-sm"),
                P(A("Volver al ingreso", href="/login", cls="text-primary hover:underline"),
                  cls=(TextPresets.muted_sm, "text-center mt-4")), id="form-recuperar")
    return listo if htmx.request else pagina("Recuperar contraseña", _tarjeta_acceso(
        "Recuperar contraseña", "Revise su correo.", listo))


def form_nueva(token, errores=()):
    return Form(
        mensaje_error(*errores),
        LabelInput("Nueva contraseña", id="nueva", type="password", required=True,
                   minlength=config.PASS_MIN_LARGO, autocomplete="new-password", autofocus=True),
        LabelInput("Repita la nueva contraseña", id="confirmacion", type="password", required=True,
                   autocomplete="new-password"),
        P(f"Mínimo {config.PASS_MIN_LARGO} caracteres, combinando letras con números o símbolos.",
          cls=TextPresets.muted_sm),
        Button("Guardar contraseña", cls=(ButtonT.primary, "w-full"), type="submit"),
        method="post", action=f"/recuperar/{token}", hx_post=f"/recuperar/{token}", hx_swap="outerHTML",
        cls="space-y-4", id="form-nueva")


def _enlace_invalido():
    return pagina("Enlace no válido", _tarjeta_acceso(
        "Enlace no válido", "El enlace venció o ya se usó.",
        P(A("Solicitar uno nuevo", href="/recuperar", cls="text-primary hover:underline"),
          cls="text-center text-sm")))


@rt("/recuperar/{token}")
def get(token: str):
    t = tokens.vigente(token)
    if not t:
        return _enlace_invalido()
    u = usuarios.por_id(t["usuario_id"])
    invitacion = t["proposito"] == "invitacion"
    return pagina("Definir contraseña", _tarjeta_acceso(
        "Bienvenido(a) al portal" if invitacion else "Nueva contraseña",
        f"{u['nombres']} {u['apellidos']} · {u['email']}", form_nueva(token)))


@rt("/recuperar/{token}")
def post(sess, htmx, token: str, nueva: str = "", confirmacion: str = ""):
    t = tokens.vigente(token)
    if not t:
        return Redirect(f"/recuperar/{token}")
    u = usuarios.por_id(t["usuario_id"])
    errores = errores_password(nueva, confirmacion, u["email"])
    if errores:
        form = form_nueva(token, errores)
        return form if htmx.request else pagina("Definir contraseña", _tarjeta_acceso(
            "Nueva contraseña", u["email"], form))
    tokens.consumir(token)
    usuarios.cambiar_password(u["id"], nueva, temporal=False)
    usuarios.desbloquear(u["email"])
    auditar(u["id"], "definir_password_enlace", "usuario", u["id"], t["proposito"])
    sess.clear()
    add_toast(sess, "Contraseña guardada. Ya puede ingresar.", "success")
    return Redirect("/login")
