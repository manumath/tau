"""Administración de cuentas: listado con búsqueda en vivo, alta, activación y restablecimiento."""
import base64
import re
import secrets
from datetime import date, datetime, timezone

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Code, Div, HtmxResponseHeaders, Option, P, Response, Select, Span,
                             Template, Thead, Tr, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Form, FormLabel, Input, Label, LabelCheckboxX, LabelInput, LabelT,
                           Table, Tbody, Td, Th, TextPresets, UkIcon)

from app.comun import (config, correo, importar_usuarios, importar_vinculos, permisos, tokens, unidades, usuarios,
                       vinculos)
from app.investigacion import perfiles
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.comun.db import auditar
from app.comun.seguridad import password_temporal

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


def opciones_categoria(actual, vacia="Sin categoría"):
    return [Option(vacia, value="", selected=not actual),
            *[Option(t, value=c, selected=c == actual) for c, t in perfiles.CATEGORIAS.items()]]


def resumen_vinculo(u):
    """Categoría vigente, aviso si falta la fecha de ingreso y botón para abrir el historial."""
    v = vinculos.vigente(u["id"])
    if v:
        texto = Span(perfiles.CATEGORIAS[v["categoria"]], cls="text-sm")
        aviso = Span(" · ingreso sin fecha", cls="text-xs text-amber-700") if not v["fecha_inicio"] else ""
    else:
        texto = Span("Sin categoría" if not vinculos.listar(u["id"]) else "Sin vínculo vigente",
                     cls="text-sm text-amber-700")
        aviso = ""
    return Div(texto, aviso,
               fh.Button(UkIcon("id-card", height=14, width=14), "Vínculo", type="button",
                         cls="inline-flex items-center gap-1 text-xs text-primary hover:underline ml-2",
                         hx_get=f"{BASE}/{u["id"]}/vinculo", hx_target=f"#{ID_MODAL}"),
               cls="flex flex-wrap items-center")


CORTO = {"administracion_sistema": "Adm. del sistema", "direccion_instituto": "Dir. Instituto",
         "direccion_carrera": "Dir. Carrera", "coordinacion_academica": "Coord. académica",
         "comite_acreditacion": "Comité de acreditación", "gestion_datos": "Gestión de datos"}


def _etiquetas_perfil(u, gestiona_roles=False):
    etiquetas = []
    if u["es_investigador"]:
        etiquetas.append(Label("Investigador", cls=LabelT.secondary))
    for r in permisos.roles_vigentes(u["id"]):
        sigla = f" · {r['sigla']}" if r["rol"] == "gestion_datos" else ""
        etiquetas.append(Label(CORTO[r["rol"]] + sigla, cls=LabelT.primary, title=permisos.nombre(r["rol"])))
    boton_roles = fh.Button(UkIcon("shield-check", height=14, width=14), "Roles", type="button",
                            cls="inline-flex items-center gap-1 text-xs text-primary hover:underline",
                            hx_get=f"{BASE}/{u['id']}/roles", hx_target=f"#{ID_MODAL}") if gestiona_roles else ""
    return Div(Div(*etiquetas, boton_roles, cls="flex gap-1 flex-wrap items-center"),
               resumen_vinculo(u) if u["es_investigador"] else "",
               cls="space-y-1")


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
    # Si tiene vínculo vigente, desactivar abre una ventana que pregunta si también termina.
    con_vinculo = u["activo"] and u["es_investigador"] and vinculos.vigente(uid)
    boton_activo = Button(
        UkIcon("user-x" if u["activo"] else "user-check", height=18, width=18),
        cls=(ButtonT.ghost, ButtonT.icon),
        aria_label="Desactivar cuenta" if u["activo"] else "Activar cuenta",
        **({"hx_get": f"/admin/usuarios/{uid}/desactivar", "hx_target": f"#{ID_MODAL}"} if con_vinculo else
           {"hx_post": f"/admin/usuarios/{uid}/activo", "hx_target": f"#usuario-{uid}", "hx_swap": "outerHTML"}),
        hx_confirm=(f"¿Desactivar la cuenta de {u['nombres']} {u['apellidos']}? "
                    "No podrá ingresar hasta que se reactive.") if u["activo"] and not con_vinculo else None,
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
        Td(_etiquetas_perfil(u, permisos.puede({"id": yo_id}, "asignar_roles"))),
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
        Div(FormLabel("Categoría (si es investigador)", fr="categoria"),
            Select(*opciones_categoria(d.get("categoria"), vacia="— Elija —"), id="categoria",
                   name="categoria", cls="uk-select"),
            P("Titulares y contratados pueden proponer proyectos institucionales y ser sus responsables; "
              "los interinos pueden ser co-responsables.", cls=TextPresets.muted_sm),
            cls="space-y-2"),
        LabelInput("Fecha de ingreso al instituto (si es investigador)", id="fecha_ingreso", type="date",
                   value=d.get("fecha_ingreso") or ""),
        Div(LabelCheckboxX("Es investigador (tendrá perfil y registrará actividad)",
                           id="es_investigador", checked=d.get("es_investigador", True)),
            LabelCheckboxX("Administración (Adm. del sistema y Dirección del Instituto; otros roles, después en «Roles»)",
                           id="es_admin",
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
    enlace = f"{config.URL_BASE}/recuperar/{tokens.emitir(u["id"], 'invitacion')}"
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
                Button(UkIcon("history", height=16, width=16), "Importar historial", cls=ButtonT.default,
                       title="Periodos de vínculo y categorías desde Recursos Humanos",
                       hx_get="/admin/usuarios/historial", hx_target=f"#{ID_MODAL}"),
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
def post(auth, nombres: str = "", apellidos: str = "", email: str = "", categoria: str = "",
         es_investigador: bool = False, es_admin: bool = False, invitar: bool = False, fecha_ingreso: str = ""):
    datos = dict(nombres=nombres.strip(), apellidos=apellidos.strip(),
                 email=email.strip().lower(), es_investigador=es_investigador, es_admin=es_admin,
                 categoria=(categoria or None) if es_investigador else None,
                 fecha_ingreso=(fecha_ingreso or None) if es_investigador else None)
    errores = []
    try:
        date.fromisoformat(fecha_ingreso) if fecha_ingreso else None
    except ValueError:
        errores.append("Fecha de ingreso no válida.")
    if not datos["nombres"] or not datos["apellidos"]:
        errores.append("Nombres y apellidos son obligatorios.")
    if not _RE_EMAIL.match(datos["email"]):
        errores.append("Ingrese un correo válido.")
    elif usuarios.por_email(datos["email"]):
        errores.append("Ya existe una cuenta con ese correo.")
    if not es_investigador and not es_admin:
        errores.append("La cuenta debe ser de investigador, de administrador o ambas.")
    if es_investigador and categoria not in perfiles.CATEGORIAS:
        errores.append("Elija la categoría del investigador(a).")
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


def modal_desactivar(u, errores=(), termina="si", fecha=""):
    v = vinculos.vigente(u["id"])
    return modal(
        "Desactivar cuenta",
        Form(mensaje_error(*errores),
             P(f"{u['nombres']} {u['apellidos']} no podrá ingresar hasta que se reactive la cuenta. Su vínculo "
               f"con el instituto ({perfiles.CATEGORIAS[v['categoria']]}, {vinculos.texto_periodo(v)}) está vigente."),
             Div(fh.Label(fh.Input(type="radio", name="termina", value="si", checked=termina == "si", cls="uk-radio"),
                          Span("Terminar también su vínculo el día", cls="text-sm"),
                          Input(type="date", name="fecha", value=fecha or date.today().isoformat(),
                                cls="uk-input w-44 ml-2", aria_label="Fecha de término"),
                          cls="flex items-center gap-2"),
                 fh.Label(fh.Input(type="radio", name="termina", value="no", checked=termina == "no", cls="uk-radio"),
                          Span("Solo desactivar la cuenta (el vínculo sigue vigente)", cls="text-sm"),
                          cls="flex items-center gap-2"),
                 cls="space-y-2"),
             P("El vínculo define qué producción cuenta para el instituto: lo publicado mientras estuvo vinculado "
               "sigue contando después.", cls=TextPresets.muted_sm),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button("Desactivar", type="submit", cls=ButtonT.destructive), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/{u["id"]}/activo", hx_target=f"#usuario-{u["id"]}", hx_swap="outerHTML",
             cls="space-y-4"))


@rt(BASE + "/{uid}/desactivar")
def get(uid: int, auth):
    u = usuarios.con_perfil(uid)
    if not u or uid == auth["id"] or not vinculos.vigente(uid):
        return ""
    return modal_desactivar(u)


@rt(BASE + "/{uid}/activo")
def post(uid: int, auth, termina: str = "", fecha: str = ""):
    u = usuarios.con_perfil(uid)
    if not u or uid == auth["id"]:
        return fila(u, auth["id"]) if u else ""
    if u["activo"] and termina == "si":
        errores = vinculos.terminar(uid, fecha)
        if errores:
            return modal_desactivar(u, errores, termina, fecha), HtmxResponseHeaders(
                retarget=f"#{ID_MODAL}", reswap="innerHTML")
        auditar(auth["id"], "terminar_vinculo", "investigador", uid, fecha)
    usuarios.set_activo(uid, not u["activo"])
    auditar(auth["id"], "desactivar_usuario" if u["activo"] else "activar_usuario", "usuario", uid)
    return fila(usuarios.con_perfil(uid), auth["id"]), Div(id=ID_MODAL, hx_swap_oob="true")


@rt(BASE + "/{uid}/categoria")
def post(uid: int, auth, sess, categoria: str = ""):
    u = usuarios.con_perfil(uid)
    if not u or not u["es_investigador"]:
        return ""
    if categoria and categoria not in perfiles.CATEGORIAS:
        return Response("Categoría no válida", status_code=400)
    perfiles.cambiar_categoria(uid, categoria or None)
    auditar(auth["id"], "cambiar_categoria", "investigador", uid,
            f"{perfiles.categoria_texto(u['categoria'])} → {perfiles.categoria_texto(categoria)}")
    add_toast(sess, f"{u['nombres']} {u['apellidos']}: {perfiles.categoria_texto(categoria)}.", "success")
    return fila(usuarios.con_perfil(uid), auth["id"])


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
          Code("email"), ", ", Code("nombres"), ", ", Code("apellidos"), " y, si quiere, ", Code("categoria"),
          " (titular, contratado, interino, invitado o externo), ", Code("investigador"),
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
        Thead(Tr(Th("Fila"), Th("Correo"), Th("Nombre"), Th("Perfil"), Th("Categoría"), Th("Estado"))),
        Tbody(*[Tr(Td(str(f["linea"]), cls=TextPresets.muted_sm), Td(f["email"]),
                   Td(f"{f['apellidos']}, {f['nombres']}"),
                   Td(", ".join(x for x, ok in (("investigador", f["es_investigador"]), ("admin", f["es_admin"])) if ok)),
                   Td(perfiles.CATEGORIAS.get(f["categoria"], "—") if f["categoria"] else "—"),
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


# --- Roles --------------------------------------------------------------------------------------------------

def _opciones_rol(elegido=""):
    """Un valor por combinación de rol y unidad permitida: 'direccion_instituto:4'."""
    opciones = [Option("— Elija un rol —", value="")]
    for rol, (nombre, siglas) in permisos.ROLES.items():
        for sigla in siglas:
            valor = f"{rol}:{unidades.id_de(sigla)}"
            opciones.append(Option(f"{nombre} · {sigla}", value=valor, selected=valor == elegido))
    return opciones


def modal_roles(u, auth, errores=(), datos=None):
    uid = u["id"]
    datos = datos or {}
    hoy = date.today().isoformat()
    filas = []
    for r in permisos.historial(uid):
        vigente = r["desde"] <= hoy and (r["hasta"] is None or r["hasta"] >= hoy)
        abierta = r["hasta"] is None or r["hasta"] >= hoy
        filas.append(Tr(
            Td(permisos.nombre(r["rol"]), Span(" · vigente", cls="text-xs text-green-700") if vigente else ""),
            Td(r["sigla"]), Td(r["desde"], cls="whitespace-nowrap"), Td(r["hasta"] or "—", cls="whitespace-nowrap"),
            Td(Div(r["nota"] or "", cls="text-sm"),
               Div(f"Asignado por {r['asignado_por_nombre']}" if r["asignado_por_nombre"] else "",
                   cls=TextPresets.muted_sm)),
            Td(Button("Quitar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                      hx_post=f"{BASE}/roles/{r['id']}/terminar", hx_target=f"#{ID_MODAL}",
                      hx_confirm=f"¿Quitar el rol {permisos.nombre(r['rol'])} ({r['sigla']}) a "
                                 f"{u['nombres']} {u['apellidos']}? Deja de regir desde hoy.") if abierta else "")))
    tabla = Table(Thead(Tr(Th("Rol"), Th("Unidad"), Th("Desde"), Th("Hasta"), Th("Nota"), Th(""))),
                  Tbody(*filas) if filas else Tbody(Tr(Td("Sin roles asignados.", colspan=6, cls=TextPresets.muted_sm))),
                  cls="uk-table-divider uk-table-small")
    ayuda = fh.Details(fh.Summary("Qué puede hacer cada rol", cls="cursor-pointer text-sm text-primary"),
                       fh.Dl(*[x for rol, d in permisos.DESCRIPCIONES.items()
                               for x in (fh.Dt(permisos.nombre(rol), cls="text-sm font-medium mt-2"),
                                         fh.Dd(d, cls=TextPresets.muted_sm))]), cls="mb-3")
    formulario = Form(
        Div(Div(FormLabel("Rol y unidad", fr="rol_unidad"),
                Select(*_opciones_rol(datos.get("rol_unidad", "")), id="rol_unidad", name="rol_unidad", cls="uk-select"),
                cls="space-y-1 sm:col-span-2"),
            LabelInput("Desde", id="rol-desde", name="desde", type="date", value=datos.get("desde") or hoy),
            LabelInput("Hasta (opcional)", id="rol-hasta", name="hasta", type="date", value=datos.get("hasta") or ""),
            cls="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end"),
        LabelInput("Pedido de", id="rol-nota", name="nota", value=datos.get("nota") or "",
                   placeholder="Dirección que lo pide y documento (nota, resolución)…"),
        Div(Button("Asignar rol", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end"),
        hx_post=f"{BASE}/{uid}/roles", hx_target=f"#{ID_MODAL}", cls="space-y-3 rounded-md border border-border p-3")
    return modal(
        f"Roles de {u['nombres']} {u['apellidos']}",
        mensaje_error(*errores),
        P("Los asigna Administración del sistema, a pedido de las direcciones. Un rol que termina queda en el "
          "historial. Investigador, docente y responsable de proyecto no se asignan: se deducen de los datos.",
          cls=(TextPresets.muted_sm, "mb-3")),
        ayuda,
        Div(tabla, cls="overflow-x-auto mb-4"),
        formulario,
        Div(Button("Listo", type="button", cls=ButtonT.default, onclick=JS_CERRAR), cls="flex justify-end mt-4"),
        Template(fila(usuarios.con_perfil(uid), auth["id"])(hx_swap_oob="true")),
        ancho="max-w-4xl")


def _puede_roles(auth):
    return permisos.puede(auth, "asignar_roles")


@rt(BASE + "/{uid}/roles")
def get(auth, uid: int):
    if not _puede_roles(auth):
        return Response("Solo Administración del sistema asigna roles.", status_code=403)
    u = usuarios.con_perfil(uid)
    return modal_roles(u, auth) if u else Response("No encontrado", status_code=404)


@rt(BASE + "/{uid}/roles")
def post(auth, uid: int, rol_unidad: str = "", desde: str = "", hasta: str = "", nota: str = ""):
    if not _puede_roles(auth):
        return Response("Solo Administración del sistema asigna roles.", status_code=403)
    u = usuarios.con_perfil(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    rol, _, unidad = rol_unidad.partition(":")
    errores = permisos.asignar(uid, rol, int(unidad) if unidad.isdigit() else 0, desde or None, hasta or None,
                               nota, auth["id"]) if rol else ["Elija un rol."]
    if not errores:
        auditar(auth["id"], "asignar_rol", "usuario", uid,
                f"{permisos.nombre(rol)} ({unidades.obtener(int(unidad))['sigla']}) desde {desde or 'hoy'}"
                + (f" hasta {hasta}" if hasta else "") + (f" · {nota.strip()}" if nota.strip() else ""))
    datos = dict(rol_unidad=rol_unidad, desde=desde, hasta=hasta, nota=nota) if errores else None
    return modal_roles(u, auth, errores, datos)


@rt(BASE + "/roles/{aid}/terminar")
def post(auth, aid: int):
    if not _puede_roles(auth):
        return Response("Solo Administración del sistema asigna roles.", status_code=403)
    a = permisos.obtener(aid)
    if not a:
        return Response("No encontrado", status_code=404)
    errores = permisos.terminar(aid)
    if not errores:
        auditar(auth["id"], "terminar_rol", "usuario", a["usuario_id"],
                f"{permisos.nombre(a['rol'])} ({unidades.obtener(a['unidad_id'])['sigla']})")
    return modal_roles(usuarios.con_perfil(a["usuario_id"]), auth, errores)


# --- Historial de vínculo ---------------------------------------------------------------------------------

def _campos_periodo(d, con_hasta=True, con_nota=True, sufijo=""):
    return Div(
        Div(FormLabel("Categoría"), Select(*opciones_categoria(d.get("categoria"), vacia="— Elija —"),
                                           name="categoria", cls="uk-select"), cls="space-y-1"),
        LabelInput("Desde", id=f"desde{sufijo}", name="desde", type="date", value=d.get("desde") or ""),
        LabelInput("Hasta", id=f"hasta{sufijo}", name="hasta", type="date", value=d.get("hasta") or "")
        if con_hasta else "",
        LabelInput("Jornada (h/semana)", id=f"jornada{sufijo}", name="jornada", type="number", min=1, max=60,
                   value=d.get("jornada") or ""),
        LabelInput("Nota", id=f"nota{sufijo}", name="nota", value=d.get("nota") or "",
                   placeholder="Resolución, contrato…") if con_nota else "",
        cls="grid grid-cols-2 sm:grid-cols-5 gap-3 items-end")


def _selector_unidad(uid, actual):
    """Pestañas IIMAT / CMAT: el historial y las acciones son de la unidad elegida."""
    return Div(*[Button(f"{x['nombre']} ({x['sigla']})", type="button",
                        cls=(ButtonT.primary if x["id"] == actual else ButtonT.default, ButtonT.sm),
                        hx_get=f"{BASE}/{uid}/vinculo?unidad={x['id']}", hx_target=f"#{ID_MODAL}",
                        aria_pressed="true" if x["id"] == actual else "false")
                 for x in unidades.con_vinculo()],
               cls="flex flex-wrap gap-2 mb-3", role="group", aria_label="Unidad")


def modal_vinculo(u, errores=(), editar=None, datos=None, yo_id=0, unidad=None):
    """Historial de periodos con una unidad y acciones: cambio de categoría, término, periodo
    histórico, corrección."""
    uid = u["id"]
    unidad = unidad or unidades.instituto()
    datos = datos or {}
    periodos = vinculos.listar(uid, unidad)
    vig = vinculos.vigente(uid, unidad=unidad)
    filas = []
    for v in periodos:
        if editar == v["id"]:
            filas.append(Tr(Td(Form(
                _campos_periodo({"categoria": v["categoria"], "desde": v["fecha_inicio"], "hasta": v["fecha_fin"],
                                 "jornada": v["jornada_horas"], "nota": v["nota"], **datos}, sufijo=f"-{v["id"]}"),
                Div(Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                           hx_get=f"{BASE}/{uid}/vinculo?unidad={unidad}", hx_target=f"#{ID_MODAL}"),
                    Button("Guardar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                    cls="flex justify-end gap-2 mt-2"),
                hx_put=f"{BASE}/vinculo/{v["id"]}", hx_target=f"#{ID_MODAL}"), colspan=5)))
            continue
        filas.append(Tr(
            Td(perfiles.CATEGORIAS[v["categoria"]], Span(" · vigente", cls="text-xs text-green-700") if vig and v["id"] == vig["id"] else ""),
            Td(v["fecha_inicio"] or Span("sin registrar", cls="text-amber-700")),
            Td(v["fecha_fin"] or "—"),
            Td(f"{v['jornada_horas']} h" if v["jornada_horas"] else "—", Span(f" · {v['nota']}", cls=TextPresets.muted_sm) if v["nota"] else ""),
            Td(Div(Button(UkIcon("pencil", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon), aria_label="Corregir",
                          title="Corregir", hx_get=f"{BASE}/vinculo/{v["id"]}/editar", hx_target=f"#{ID_MODAL}"),
                   Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon), aria_label="Eliminar",
                          title="Eliminar (solo para corregir errores)", hx_delete=f"{BASE}/vinculo/{v["id"]}",
                          hx_target=f"#{ID_MODAL}", hx_confirm="¿Eliminar este periodo? Úselo solo para corregir errores."),
                   cls="flex justify-end"))))
    tabla = Table(Thead(Tr(Th("Categoría"), Th("Desde"), Th("Hasta"), Th("Jornada"), Th(""))),
                  Tbody(*filas) if filas else Tbody(Tr(Td("Sin periodos registrados.", colspan=5,
                                                          cls=TextPresets.muted_sm))),
                  cls="uk-table-divider uk-table-small")

    def accion(titulo, *campos, url, boton):
        return fh.Details(fh.Summary(titulo, cls="cursor-pointer text-sm font-medium text-primary"),
                          Form(*campos, Input(type="hidden", name="unidad", value=str(unidad)),
                               Div(Button(boton, type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                                            cls="flex justify-end mt-2"),
                               hx_post=url, hx_target=f"#{ID_MODAL}", cls="mt-2"),
                          cls="rounded-md border border-border p-3")
    acciones = [
        accion("Cambiar de categoría (ascenso, nuevo contrato)",
               P("Cierra el periodo vigente el día anterior y abre uno nuevo.", cls=TextPresets.muted_sm),
               _campos_periodo(datos, con_hasta=False, con_nota=False, sufijo="-cambio"),
               url=f"{BASE}/{uid}/vinculo/cambio", boton="Registrar cambio") if vig else "",
        accion("Terminar el vínculo",
               LabelInput("Último día", id="fecha-termino", name="fecha", type="date", value=date.today().isoformat()),
               url=f"{BASE}/{uid}/vinculo/termino", boton="Terminar") if vig else "",
        accion("Agregar un periodo (histórico o nuevo ingreso)",
               _campos_periodo(datos, sufijo="-nuevo"), url=f"{BASE}/{uid}/vinculo/periodo", boton="Agregar"),
    ]
    return modal(
        f"Vínculo de {u['nombres']} {u['apellidos']}",
        mensaje_error(*errores),
        P("Periodos de pertenencia a cada unidad con su categoría y jornada. El vínculo con el Instituto define "
          "qué producción cuenta en los informes de investigación y con qué categoría; el de la Carrera, la "
          "docencia. Para cargar el historial de muchas personas, use «Importar historial» en el listado.",
          cls=(TextPresets.muted_sm, "mb-3")),
        _selector_unidad(uid, unidad),
        Div(tabla, cls="overflow-x-auto mb-4"),
        Div(*acciones, cls="space-y-2"),
        Div(Button("Listo", type="button", cls=ButtonT.default, onclick=JS_CERRAR), cls="flex justify-end mt-4"),
        Template(fila(usuarios.con_perfil(uid), yo_id)(hx_swap_oob="true")),
        ancho="max-w-4xl")


def _investigador(uid):
    u = usuarios.con_perfil(uid)
    return u if u and u["es_investigador"] else None


def _unidad_valida(valor) -> int | None:
    """Id de una unidad con vínculo (IIMAT o CMAT); None si no lo es (se usa el Instituto)."""
    ids = {x["id"] for x in unidades.con_vinculo()}
    return int(valor) if str(valor).isdigit() and int(valor) in ids else None


def _sigla(unidad):
    return unidades.obtener(unidad or unidades.instituto())["sigla"]


@rt(BASE + "/{uid}/vinculo")
def get(auth, uid: int, unidad: str = ""):
    u = _investigador(uid)
    return modal_vinculo(u, yo_id=auth["id"], unidad=_unidad_valida(unidad)) if u \
        else Response("No encontrado", status_code=404)


@rt(BASE + "/{uid}/vinculo/cambio")
def post(auth, uid: int, categoria: str = "", desde: str = "", jornada: str = "", unidad: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    un = _unidad_valida(unidad)
    errores = vinculos.cambiar_categoria(uid, categoria, desde, jornada or None, auth["id"], unidad=un)
    if not errores:
        auditar(auth["id"], "cambiar_categoria", "investigador", uid, f"{_sigla(un)}: {categoria} desde {desde}")
    return modal_vinculo(u, errores, yo_id=auth["id"], unidad=un,
                         datos={"categoria": categoria, "desde": desde, "jornada": jornada} if errores else None)


@rt(BASE + "/{uid}/vinculo/termino")
def post(auth, uid: int, fecha: str = "", unidad: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    un = _unidad_valida(unidad)
    errores = vinculos.terminar(uid, fecha, unidad=un)
    if not errores:
        auditar(auth["id"], "terminar_vinculo", "investigador", uid, f"{_sigla(un)}: {fecha}")
    return modal_vinculo(u, errores, yo_id=auth["id"], unidad=un)


@rt(BASE + "/{uid}/vinculo/periodo")
def post(auth, uid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = "", nota: str = "",
         unidad: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    un = _unidad_valida(unidad)
    errores = vinculos.agregar(uid, categoria, desde or None, hasta or None, jornada or None, nota, auth["id"],
                               unidad=un)
    if not errores:
        auditar(auth["id"], "agregar_vinculo", "investigador", uid,
                f"{_sigla(un)}: {categoria} {desde or '?'} a {hasta or 'hoy'}")
    datos = dict(categoria=categoria, desde=desde, hasta=hasta, jornada=jornada, nota=nota) if errores else None
    return modal_vinculo(u, errores, datos=datos, yo_id=auth["id"], unidad=un)


@rt(BASE + "/vinculo/{vid}/editar")
def get(auth, vid: int):
    v = vinculos.obtener(vid)
    if not v:
        return Response("No encontrado", status_code=404)
    return modal_vinculo(_investigador(v["usuario_id"]), editar=vid, yo_id=auth["id"], unidad=v["unidad_id"])


@rt(BASE + "/vinculo/{vid}")
def put(auth, vid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = "", nota: str = ""):
    v = vinculos.obtener(vid)
    if not v:
        return Response("No encontrado", status_code=404)
    errores = vinculos.editar(vid, categoria, desde or None, hasta or None, jornada or None, nota)
    if not errores:
        auditar(auth["id"], "corregir_vinculo", "investigador", v["usuario_id"],
                f"{categoria} {desde or '?'} a {hasta or 'hoy'}")
    u = _investigador(v["usuario_id"])
    if errores:
        return modal_vinculo(u, errores, editar=vid, yo_id=auth["id"], unidad=v["unidad_id"],
                             datos=dict(categoria=categoria, desde=desde, hasta=hasta, jornada=jornada, nota=nota))
    return modal_vinculo(u, yo_id=auth["id"], unidad=v["unidad_id"])


@rt(BASE + "/vinculo/{vid}")
def delete(auth, vid: int):
    v = vinculos.obtener(vid)
    if not v:
        return Response("No encontrado", status_code=404)
    vinculos.eliminar(vid)
    auditar(auth["id"], "eliminar_vinculo", "investigador", v["usuario_id"],
            f"{_sigla(v['unidad_id'])}: {vinculos.texto_periodo(v)}")
    return modal_vinculo(_investigador(v["usuario_id"]), yo_id=auth["id"], unidad=v["unidad_id"])


# --- Historial de vínculos desde Recursos Humanos (CSV) -----------------------------------------------------

def _form_historial(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Suba un CSV de Recursos Humanos con una fila por periodo: ", Code("email"), ", ", Code("categoria"), ", ",
          Code("desde"), " y, si quiere, ", Code("hasta"), " (vacío = vigente), ", Code("jornada"), " (horas "
          "semanales), ", Code("nota"), " y ", Code("unidad"), " (IIMAT o CMAT; vacío = IIMAT). Fechas como "
          "AAAA-MM-DD o DD/MM/AAAA.", cls="text-sm"),
        P("El historial de cada persona con cada unidad del archivo se reemplaza por el del archivo; lo demás no "
          "cambia. Primero verá una vista previa.", cls=TextPresets.muted_sm),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href="/admin/usuarios/historial/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
            Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_post="/admin/usuarios/historial/revisar", hx_encoding="multipart/form-data",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


@rt(f"{BASE}/historial")
def get():
    return modal("Importar historial de vínculos", _form_historial(), ancho="max-w-2xl")


@rt(f"{BASE}/historial/plantilla")
def get():
    return Response(importar_vinculos.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-historial.csv"'})


@rt(f"{BASE}/historial/revisar")
async def post(archivo: UploadFile = None):
    if archivo is None or not archivo.filename:
        return modal("Importar historial de vínculos", _form_historial(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar_vinculos.MAX_BYTES + 1)
    personas, errores = importar_vinculos.leer(contenido)
    if not personas:
        return modal("Importar historial de vínculos", _form_historial(errores), ancho="max-w-2xl")
    listas = [p for p in personas if not p["errores"]]
    filas = []
    for p in personas:
        nombre = f"{p['usuario']['apellidos']}, {p['usuario']['nombres']}" if p["usuario"] else p["email"]
        periodos = "; ".join(f"{perfiles.CATEGORIAS[x['categoria']]} {x['desde']} a {x['hasta'] or 'hoy'}"
                             for x in p["periodos"])
        filas.append(Tr(Td(Div(nombre, cls="font-medium"), Div(p["email"], cls=TextPresets.muted_sm)),
                        Td(p["unidad"], cls="text-sm"),
                        Td(periodos or "—", cls="text-sm"),
                        Td(Label("Error", cls=LabelT.destructive), Div(*[P(e, cls="text-sm") for e in p["errores"]])
                           if p["errores"] else
                           Span(f"Reemplaza {p['actuales']} periodo(s) actual(es)", cls="text-sm"))))
    return modal(
        "Vista previa del historial",
        P(f"{len(listas)} persona(s) se actualizarán · {len(personas) - len(listas)} con errores, se omiten.",
          cls="text-sm font-medium mb-3"),
        Div(Table(Thead(Tr(Th("Persona"), Th("Unidad"), Th("Periodos del archivo"), Th("Resultado"))), Tbody(*filas),
                  cls="uk-table-divider uk-table-small"),
            cls="max-h-96 overflow-y-auto border border-border rounded-md mb-4"),
        Form(Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button(f"Actualizar {len(listas)} persona(s)", type="submit", cls=ButtonT.primary,
                        disabled=not listas), cls="flex justify-end gap-2"),
             hx_post="/admin/usuarios/historial/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-4xl")


@rt(f"{BASE}/historial/confirmar")
def post(auth, sess, contenido: str = ""):
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return modal("Importar historial de vínculos", _form_historial(["No se pudo leer el archivo. Súbalo otra vez."]))
    personas, _ = importar_vinculos.leer(datos)
    n = importar_vinculos.aplicar(personas, auth["id"])
    add_toast(sess, f"Historial actualizado para {n} persona(s).", "success")
    return (modal("Historial importado", P(f"Se actualizó el historial de {n} persona(s)."),
                  Div(Button("Listo", cls=ButtonT.primary, onclick=JS_CERRAR, type="button"),
                      cls="flex justify-end mt-4")),
            Template(cuerpo_tabla(usuarios.listar(), auth["id"], oob=True)))
