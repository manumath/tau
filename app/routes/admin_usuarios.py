"""Administración de cuentas: listado con búsqueda en vivo, alta, activación y restablecimiento."""
import base64
import re
import secrets
from datetime import datetime, timezone

from fasthtml.common import A, APIRouter, Code, Div, P, Response, Span, Template, Thead, Tr, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Form, Input, Label, LabelCheckboxX, LabelInput, LabelT,
                           Table, Tbody, Td, Th, TextPresets, UkIcon)

from app import config, correo, importar_usuarios, tokens, usuarios
from app.components.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.db import auditar
from app.seguridad import password_temporal

rt = APIRouter()
BASE = "/admin/usuarios"

ID_TBODY = "tabla-usuarios"
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --- Componentes -------------------------------------------------------------

def fecha_local(iso_utc: str | None) -> str:
    """SQLite guarda UTC ('2026-09-24 02:38:11'); se muestra en la hora local del servidor."""
    if not iso_utc:
        return "—"
    dt = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc).astimezone()
    return dt.strftime("%d-%m-%Y %H:%M")


def _etiquetas_perfil(u):
    etiquetas = []
    if u["es_investigador"]:
        etiquetas.append(Label("Investigador", cls=LabelT.secondary))
    if u["es_admin"]:
        etiquetas.append(Label("Admin", cls=LabelT.primary))
    return Div(*etiquetas, cls="flex gap-1 flex-wrap")


def _estado(u, bloqueada=False):
    if not u["activo"]:
        return Label("Inactiva", cls=LabelT.destructive)
    if bloqueada:
        return Span(UkIcon("lock", height=14, width=14), "Bloqueada por intentos fallidos",
                    title=f"Se desbloquea sola a los {config.LOGIN_VENTANA_MIN} minutos, o con el botón del candado.",
                    cls="inline-flex items-center gap-1 text-red-600 text-sm whitespace-nowrap")
    if u["debe_cambiar_pass"]:
        return Span(UkIcon("clock", height=14, width=14), "Sin primer ingreso",
                    cls="inline-flex items-center gap-1 text-amber-600 text-sm whitespace-nowrap")
    return Span(UkIcon("check", height=14, width=14), "Activa",
                cls="inline-flex items-center gap-1 text-green-600 text-sm")


def fila(u, yo_id: int):
    uid = u["id"]
    es_yo = uid == yo_id
    bloqueada = usuarios.bloqueado(u["email"])
    boton_desbloquear = Button(
        UkIcon("lock-open", height=18, width=18), cls=(ButtonT.ghost, ButtonT.icon),
        aria_label="Desbloquear", title="Desbloquear (sin cambiar la contraseña)",
        hx_post=f"/admin/usuarios/{uid}/desbloquear", hx_target=f"#usuario-{uid}",
        hx_swap="outerHTML") if bloqueada else ""
    boton_activo = Button(
        UkIcon("user-x" if u["activo"] else "user-check", height=18, width=18),
        cls=(ButtonT.ghost, ButtonT.icon),
        aria_label="Desactivar cuenta" if u["activo"] else "Activar cuenta",
        hx_post=f"/admin/usuarios/{uid}/activo", hx_target=f"#usuario-{uid}", hx_swap="outerHTML",
        hx_confirm=(f"¿Desactivar la cuenta de {u['nombres']} {u['apellidos']}? "
                    "No podrá ingresar hasta que se reactive.") if u["activo"] else None,
        disabled=es_yo,
        title="No puede desactivar su propia cuenta" if es_yo else
              ("Desactivar cuenta" if u["activo"] else "Activar cuenta"))
    boton_reset = Button(
        UkIcon("key-round", height=18, width=18),
        cls=(ButtonT.ghost, ButtonT.icon), aria_label="Restablecer contraseña",
        hx_post=f"/admin/usuarios/{uid}/restablecer", hx_target=f"#{ID_MODAL}",
        hx_confirm=f"¿Generar una nueva contraseña temporal para {u['email']}? "
                   "La actual dejará de funcionar.",
        disabled=es_yo,
        title="Use «Contraseña» en el menú para cambiar la suya" if es_yo else
              "Restablecer contraseña")
    return Tr(
        Td(Div(f"{u['apellidos']}, {u['nombres']}", cls="font-medium"),
           Div("(usted)", cls=TextPresets.muted_sm) if es_yo else ""),
        Td(u["email"]),
        Td(_etiquetas_perfil(u)),
        Td(_estado(u, bloqueada)),
        Td(fecha_local(u["ultimo_acceso"]),
           cls=(TextPresets.muted_sm, "whitespace-nowrap hidden lg:table-cell")),
        Td(Div(boton_desbloquear, boton_activo, boton_reset, cls="flex gap-1 justify-end")),
        id=f"usuario-{uid}")


def cuerpo_tabla(lista, yo_id, oob=False):
    filas = [fila(u, yo_id) for u in lista] or [
        Tr(Td("No hay usuarios que coincidan con la búsqueda.", colspan=6,
              cls=(TextPresets.muted_sm, "text-center py-6")))]
    return Tbody(*filas, id=ID_TBODY, hx_swap_oob="true" if oob else None)


def form_usuario(datos=None, errores=()):
    d = datos or {}
    return Form(
        mensaje_error(*errores),
        Div(LabelInput("Nombres", id="nombres", value=d.get("nombres", ""), required=True),
            LabelInput("Apellidos", id="apellidos", value=d.get("apellidos", ""), required=True),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        LabelInput("Correo institucional", id="email", type="email", value=d.get("email", ""),
                   required=True),
        Div(LabelCheckboxX("Es investigador (tendrá perfil y registrará actividad)",
                           id="es_investigador", checked=d.get("es_investigador", True)),
            LabelCheckboxX("Administrador del portal", id="es_admin",
                           checked=d.get("es_admin", False)),
            cls="space-y-2"),
        Div(LabelCheckboxX("Enviar invitación por correo", id="invitar",
                           checked=d.get("invitar", config.CORREO_MODO != "desactivado")),
            P("Con invitación, la persona recibe un enlace (válido 3 días) para definir su contraseña y "
              "nadie más la conoce. Sin invitación, se muestra una contraseña temporal para entregarla "
              "a mano; deberá cambiarla en su primer ingreso.", cls=TextPresets.muted_sm),
            cls="space-y-1 rounded-md border border-border p-3"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
            Button("Crear cuenta", type="submit", cls=ButtonT.primary),
            cls="flex justify-end gap-2"),
        hx_post="/admin/usuarios", hx_target=f"#{ID_MODAL}", cls="space-y-4")


def modal_credenciales(titulo, u, password, nota):
    """Muestra la contraseña temporal una sola vez para que el admin la entregue."""
    return modal(
        titulo,
        Div(P(f"{u['nombres']} {u['apellidos']}", cls="font-medium"),
            P(u["email"], cls=TextPresets.muted_sm),
            cls="mb-4"),
        Div(Span("Contraseña temporal", cls=TextPresets.muted_sm),
            Div(Code(password, id="pass-temporal", cls="text-lg font-mono tracking-wide"),
                Button(UkIcon("copy", height=16, width=16), "Copiar", cls=ButtonT.ghost,
                       type="button",
                       onclick="navigator.clipboard.writeText("
                               "document.getElementById('pass-temporal').innerText);"
                               "this.lastChild.textContent=' Copiada'"),
                cls="flex items-center justify-between"),
            cls="rounded-md border border-border p-4 bg-muted/40"),
        P(nota, cls=(TextPresets.muted_sm, "mt-3")),
        Div(Button("Listo", cls=ButtonT.primary, onclick=JS_CERRAR, type="button"),
            cls="flex justify-end mt-4"))


def enviar_invitacion(u):
    enlace = f"{config.URL_BASE}/recuperar/{tokens.emitir(u['id'], 'invitacion')}"
    correo.enviar(u["email"], f"Invitación al Portal de Investigación · {config.NOMBRE_INSTITUTO}",
                  f"Hola, {u['nombres']}:\n\nSe creó su cuenta en el Portal de Investigación del instituto. "
                  f"Para definir su contraseña, abra este enlace (vale una vez y durante 3 días):\n\n{enlace}\n\n"
                  f"Luego podrá ingresar con su correo ({u['email']}).")


# --- Rutas -------------------------------------------------------------------

@rt(BASE)
def get(auth, q: str = ""):
    buscador = Input(
        type="search", name="q", value=q, placeholder="Buscar por nombre o correo…",
        hx_get="/admin/usuarios/filas", hx_target=f"#{ID_TBODY}", hx_swap="outerHTML",
        hx_trigger="input changed delay:300ms, search", hx_indicator="#buscando",
        cls="max-w-sm", aria_label="Buscar usuarios")
    return pagina(
        "Usuarios",
        Div(Div(H2("Usuarios"),
                P("Cuentas con acceso al portal.", cls=TextPresets.muted_sm)),
            Div(Button(UkIcon("file-up", height=16, width=16), "Importar CSV", cls=ButtonT.default,
                       hx_get="/admin/usuarios/importar", hx_target=f"#{ID_MODAL}"),
                Button(UkIcon("user-plus", height=16, width=16), "Nuevo usuario", cls=ButtonT.primary,
                       hx_get="/admin/usuarios/nuevo", hx_target=f"#{ID_MODAL}"),
                cls="flex gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(buscador,
            Span(UkIcon("loader-circle", height=16, width=16, cls="animate-spin"),
                 id="buscando", cls="htmx-indicator"),
            cls="flex items-center gap-2 mb-4"),
        Div(Table(Thead(Tr(Th("Nombre"), Th("Correo"), Th("Perfil"), Th("Estado"),
                           Th("Último acceso", cls="hidden lg:table-cell"), Th(""))),
                  cuerpo_tabla(usuarios.listar(q), auth["id"]),
                  cls="uk-table-middle uk-table-divider uk-table-hover"),
            cls="overflow-x-auto"),
        usuario=auth, seccion="usuarios")


@rt(f"{BASE}/filas")
def get(auth, q: str = ""):
    return cuerpo_tabla(usuarios.listar(q), auth["id"])


@rt(f"{BASE}/nuevo")
def get():
    return modal("Nuevo usuario", form_usuario())


@rt(BASE)
def post(auth, nombres: str = "", apellidos: str = "", email: str = "",
         es_investigador: bool = False, es_admin: bool = False, invitar: bool = False):
    datos = dict(nombres=nombres.strip(), apellidos=apellidos.strip(),
                 email=email.strip().lower(), es_investigador=es_investigador, es_admin=es_admin)
    errores = []
    if not datos["nombres"] or not datos["apellidos"]:
        errores.append("Nombres y apellidos son obligatorios.")
    if not _RE_EMAIL.match(datos["email"]):
        errores.append("Ingrese un correo válido.")
    elif usuarios.por_email(datos["email"]):
        errores.append("Ya existe una cuenta con ese correo.")
    if not es_investigador and not es_admin:
        errores.append("La cuenta debe ser de investigador, de administrador o ambas.")
    if errores:
        return modal("Nuevo usuario", form_usuario({**datos, "invitar": invitar}, errores))

    tabla = Template(cuerpo_tabla(usuarios.listar(), auth["id"], oob=True))
    if invitar:
        # Contraseña aleatoria que nadie conoce: la persona define la suya con el enlace.
        u = usuarios.crear(password=secrets.token_urlsafe(24), debe_cambiar_pass=False, **datos)
        auditar(auth["id"], "crear_usuario", "usuario", u["id"], f"{datos['email']} (invitación)")
        enviar_invitacion(u)
        return (modal("Invitación enviada",
                      P(f"Enviamos a {u['email']} un enlace para que {u['nombres']} defina su contraseña. "
                        "Vale 3 días; si vence, use «Restablecer» o pídale que use «¿Olvidó su contraseña?»."),
                      Div(Button("Listo", cls=ButtonT.primary, onclick=JS_CERRAR, type="button"),
                          cls="flex justify-end mt-4")),
                tabla)
    password = password_temporal()
    u = usuarios.crear(password=password, **datos)
    auditar(auth["id"], "crear_usuario", "usuario", u["id"], datos["email"])
    return (modal_credenciales("Cuenta creada", u, password,
                               "Entréguela al usuario por un canal seguro. No se volverá a mostrar."),
            # Los elementos de tabla OOB deben ir en <template>: sueltos, el parser HTML los descarta.
            tabla)


@rt(BASE + "/{uid}/activo")
def post(uid: int, auth):
    u = usuarios.por_id(uid)
    if u and uid != auth["id"]:
        usuarios.set_activo(uid, not u["activo"])
        auditar(auth["id"], "desactivar_usuario" if u["activo"] else "activar_usuario",
                "usuario", uid)
    return fila(usuarios.con_perfil(uid), auth["id"]) if u else ""


@rt(BASE + "/{uid}/desbloquear")
def post(uid: int, auth, sess):
    u = usuarios.con_perfil(uid)
    if not u:
        return ""
    usuarios.desbloquear(u["email"])
    auditar(auth["id"], "desbloquear_usuario", "usuario", uid)
    add_toast(sess, f"Cuenta de {u['nombres']} {u['apellidos']} desbloqueada. Su contraseña no cambió.", "success")
    return fila(u, auth["id"])


@rt(BASE + "/{uid}/restablecer")
def post(uid: int, auth):
    u = usuarios.con_perfil(uid)
    if not u or uid == auth["id"]:
        return ""
    password = password_temporal()
    usuarios.cambiar_password(uid, password, temporal=True)
    usuarios.desbloquear(u["email"])
    auditar(auth["id"], "restablecer_password", "usuario", uid)
    u = usuarios.con_perfil(uid)
    return (modal_credenciales("Contraseña restablecida", u, password,
                               "La contraseña anterior dejó de funcionar. El usuario deberá "
                               "definir una nueva al ingresar."),
            Template(fila(u, auth["id"])(hx_swap_oob="true")))


# --- Carga masiva desde CSV ------------------------------------------------------------------

def _form_archivo(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Suba un archivo CSV (se puede exportar desde Excel) con una fila por persona y las columnas ",
          Code("email"), ", ", Code("nombres"), ", ", Code("apellidos"), " y, si quiere, ", Code("investigador"),
          " y ", Code("admin"), " (sí/no). Primero verá una vista previa: no se crea nada hasta confirmar.",
          cls="text-sm"),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href="/admin/usuarios/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
            Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_post="/admin/usuarios/importar/revisar", hx_encoding="multipart/form-data",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


@rt(f"{BASE}/importar")
def get():
    return modal("Importar cuentas desde CSV", _form_archivo(), ancho="max-w-2xl")


@rt(f"{BASE}/plantilla")
def get():
    return Response(importar_usuarios.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-usuarios.csv"'})


def _etiqueta_estado(f):
    if f["estado"] == "nueva":
        return Label("Nueva", cls=LabelT.primary)
    if f["estado"] == "existe":
        return Label("Ya existe", cls=LabelT.secondary)
    return Label("Error", cls=LabelT.destructive)


@rt(f"{BASE}/importar/revisar")
async def post(archivo: UploadFile = None):
    if archivo is None or not archivo.filename:
        return modal("Importar cuentas desde CSV", _form_archivo(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar_usuarios.MAX_BYTES + 1)
    filas, errores = importar_usuarios.leer(contenido)
    if not filas:
        return modal("Importar cuentas desde CSV", _form_archivo(errores), ancho="max-w-2xl")
    nuevas = sum(f["estado"] == "nueva" for f in filas)
    con_error = sum(f["estado"] == "error" for f in filas)
    existentes = sum(f["estado"] == "existe" for f in filas)
    tabla = Table(
        Thead(Tr(Th("Fila"), Th("Correo"), Th("Nombre"), Th("Perfil"), Th("Estado"))),
        Tbody(*[Tr(Td(str(f["linea"]), cls=TextPresets.muted_sm), Td(f["email"]),
                   Td(f"{f['apellidos']}, {f['nombres']}"),
                   Td(", ".join(x for x, ok in (("investigador", f["es_investigador"]), ("admin", f["es_admin"])) if ok)),
                   Td(_etiqueta_estado(f), Span(f" {f['mensaje']}", cls="text-sm") if f["mensaje"] else ""))
                for f in filas]),
        cls="uk-table-divider uk-table-small")
    return modal(
        "Vista previa de la importación",
        mensaje_error(*errores),
        P(f"{nuevas} cuenta(s) nueva(s) · {existentes} ya existente(s), se omiten · {con_error} con error, se omiten.",
          cls="text-sm font-medium mb-3"),
        Div(tabla, cls="max-h-80 overflow-y-auto border border-border rounded-md mb-4"),
        Form(
            # El contenido viaja de vuelta en base64 y se valida otra vez al confirmar.
            Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
            LabelCheckboxX("Enviar invitaciones por correo (cada persona define su contraseña)", id="invitar",
                           checked=config.CORREO_MODO != "desactivado"),
            P("Sin invitación, se mostrará una contraseña temporal por cuenta para entregarla a mano.",
              cls=TextPresets.muted_sm),
            Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                Button(f"Crear {nuevas} cuenta(s)", type="submit", cls=ButtonT.primary, disabled=not nuevas),
                cls="flex justify-end gap-2"),
            hx_post="/admin/usuarios/importar/confirmar", hx_target=f"#{ID_MODAL}", cls="space-y-2"),
        ancho="max-w-4xl")


@rt(f"{BASE}/importar/confirmar")
def post(auth, sess, contenido: str = "", invitar: bool = False):
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return modal("Importar cuentas desde CSV", _form_archivo(["No se pudo leer el archivo. Súbalo otra vez."]))
    filas, _ = importar_usuarios.leer(datos)
    creadas = importar_usuarios.crear(filas, invitar, auth["id"], enviar_invitacion)
    tabla = Template(cuerpo_tabla(usuarios.listar(), auth["id"], oob=True))
    add_toast(sess, f"{len(creadas)} cuenta(s) creada(s).", "success")
    if invitar or not creadas:
        cuerpo = P(f"Se crearon {len(creadas)} cuenta(s)" + (" y se enviaron las invitaciones por correo (válidas 3 días)."
                                                            if invitar and creadas else "."))
    else:
        credenciales = "\n".join(f"{u['email']}\t{u['password']}" for u in creadas)
        cuerpo = Div(
            P("Entregue cada contraseña temporal por un canal seguro: no se volverán a mostrar. "
              "Deberán cambiarla en su primer ingreso.", cls="text-sm mb-3"),
            Div(Table(Thead(Tr(Th("Correo"), Th("Contraseña temporal"))),
                      Tbody(*[Tr(Td(u["email"]), Td(Code(u["password"], cls="font-mono"))) for u in creadas]),
                      cls="uk-table-divider uk-table-small"),
                cls="max-h-80 overflow-y-auto border border-border rounded-md"),
            Button(UkIcon("copy", height=16, width=16), "Copiar todo (correo y contraseña)", type="button",
                   cls=(ButtonT.default, "mt-3"), data_credenciales=credenciales,
                   onclick="navigator.clipboard.writeText(this.dataset.credenciales);"
                           "this.lastChild.textContent=' Copiado'"))
    return (modal("Importación terminada", cuerpo,
                  Div(Button("Listo", cls=ButtonT.primary, onclick=JS_CERRAR, type="button"),
                      cls="flex justify-end mt-4"), ancho="max-w-2xl"),
            tabla)
