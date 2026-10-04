"""Cuentas: listado con búsqueda en vivo, alta (con invitación o contraseña temporal),
activación, categoría, desbloqueo y restablecimiento de la contraseña."""
import re
import secrets
from datetime import date

import fasthtml.common as fh
from fasthtml.common import APIRouter, Code, Div, HtmxResponseHeaders, Option, P, Response, Select, Span, Template, Thead, Tr
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Form, FormLabel, Input, LabelCheckboxX, LabelInput, Table, Th,
                           TextPresets, UkIcon)

from app.comun import config, correo, permisos, tokens, usuarios, vinculos
from app.comun.componentes.avisos_emergentes import aviso_con_deshacer
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.db import auditar
from app.comun.rutas.admin_usuarios.comun import (BASE, ID_TBODY, SIN_PERMISO, cuerpo_tabla, fila, gestiona_vinculos,
                                                  opciones_categoria)
from app.comun.rutas.admin_usuarios.vinculo import AYUDA_TERMINO
from app.comun.seguridad import password_temporal

rt = APIRouter()
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def form_usuario(datos=None, errores=(), con_vinculo=False):
    """`con_vinculo`: quien crea la cuenta define también la categoría (solo la Dirección de Carrera)."""
    d = datos or {}
    vinculo = Div(
        Div(FormLabel("Categoría (si es investigador o docente)", fr="categoria"),
            Select(*opciones_categoria(d.get("categoria"), vacia="— Sin vínculo por ahora —"), id="categoria",
                   name="categoria", cls="uk-select"),
            P("Titulares y contratados pueden proponer proyectos institucionales y ser sus responsables; "
              "los interinos pueden ser co-responsables. La carga horaria se registra después, en «Vínculo».",
              cls=TextPresets.muted_sm),
            cls="space-y-2"),
        Div(LabelInput("Fecha de ingreso", id="fecha_ingreso", type="date", value=d.get("fecha_ingreso") or ""),
            LabelInput("Fecha de término", id="fecha_termino", type="date", value=d.get("fecha_termino") or ""),
            cls="grid grid-cols-2 gap-4"),
        P(AYUDA_TERMINO, cls=TextPresets.muted_sm),
        cls="space-y-4") if con_vinculo else P(
            UkIcon("info", height=14, width=14, cls="shrink-0 mt-0.5"),
            Span("La categoría y el vínculo (ingreso, carga horaria) los define la Dirección de Carrera en «Vínculo»."),
            cls=(TextPresets.muted_sm, "flex items-start gap-1"))
    return Form(
        mensaje_error(*errores),
        Div(LabelInput("Nombres", id="nombres", value=d.get("nombres", ""), required=True),
            LabelInput("Apellidos", id="apellidos", value=d.get("apellidos", ""), required=True),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        LabelInput("Correo institucional", id="email", type="email", value=d.get("email", ""),
                   required=True),
        vinculo,
        Div(LabelCheckboxX("Es investigador (tendrá perfil y registrará actividad)",
                           id="es_investigador", checked=d.get("es_investigador", True)),
            LabelCheckboxX("Sin acceso al sistema (se registran solo sus datos, p. ej., un docente que no lo usa)",
                           id="sin_acceso", checked=d.get("sin_acceso", False)),
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
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
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
                       data_accion="copiar", data_copiar_de="pass-temporal", data_copiado="Copiada"),
                cls="flex items-center justify-between"),
            cls="rounded-md border border-border p-4 bg-muted/40"),
        P(nota, cls=(TextPresets.muted_sm, "mt-3")),
        Div(Button("Listo", cls=ButtonT.primary, data_accion="cerrar-modal", type="button"),
            cls="flex justify-end mt-4"))


def enviar_invitacion(u):
    enlace = f"{config.URL_BASE}/recuperar/{tokens.emitir(u["id"], 'invitacion')}"
    correo.enviar(u["email"], f"Invitación a {config.NOMBRE_SISTEMA} · {config.DESCRIPCION_SISTEMA}",
                  f"Hola, {u['nombres']}:\n\nSe creó su cuenta en {config.NOMBRE_COMPLETO}. "
                  f"Para definir su contraseña, abra este enlace (vale una vez y durante 3 días):\n\n{enlace}\n\n"
                  f"Luego podrá ingresar con su correo ({u['email']}).")


# --- Rutas -------------------------------------------------------------------

@rt(BASE)
def get(auth, q: str = ""):
    cuentas = permisos.puede(auth, "administrar_cuentas")
    buscador = Input(
        type="search", name="q", value=q, placeholder="Buscar por nombre o correo…",
        hx_get="/admin/usuarios/filas", hx_target=f"#{ID_TBODY}", hx_swap="outerHTML",
        hx_trigger="input changed delay:300ms, search", hx_indicator="#buscando",
        cls="max-w-sm", aria_label="Buscar usuarios")
    return pagina(
        "Usuarios",
        Div(Div(H2("Usuarios"),
                P("Cuentas con acceso al sistema.", cls=TextPresets.muted_sm)),
            Div(Button(UkIcon("file-up", height=16, width=16), "Importar CSV", cls=ButtonT.default,
                       hx_get="/admin/usuarios/importar", hx_target=f"#{ID_MODAL}") if cuentas else "",
                Button(UkIcon("history", height=16, width=16), "Importar historial", cls=ButtonT.default,
                       title="Periodos de vínculo y categorías desde Recursos Humanos",
                       hx_get="/admin/usuarios/historial", hx_target=f"#{ID_MODAL}")
                if gestiona_vinculos(auth) else "",
                Button(UkIcon("user-plus", height=16, width=16), "Nuevo usuario", cls=ButtonT.primary,
                       hx_get="/admin/usuarios/nuevo", hx_target=f"#{ID_MODAL}") if cuentas else "",
                cls="flex gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(buscador,
            Span(UkIcon("loader-circle", height=16, width=16, cls="animate-spin"),
                 id="buscando", cls="htmx-indicator"),
            cls="flex items-center gap-2 mb-4"),
        Div(Table(Thead(Tr(Th("Nombre"), Th("Correo"), Th("Perfil"), Th("Estado"),
                           Th("Último acceso", cls="hidden lg:table-cell"), Th(""))),
                  cuerpo_tabla(usuarios.listar(q), auth),
                  cls="uk-table-middle uk-table-divider uk-table-hover", data_tabla="usuarios", data_tabla_filtro="no"),
            cls="overflow-x-auto"),
        usuario=auth, seccion="usuarios")


@rt(f"{BASE}/filas")
def get(auth, q: str = ""):
    return cuerpo_tabla(usuarios.listar(q), auth)


@rt(f"{BASE}/nuevo")
def get(auth):
    return modal("Nuevo usuario", form_usuario(con_vinculo=gestiona_vinculos(auth)))


@rt(BASE)
def post(auth, nombres: str = "", apellidos: str = "", email: str = "", categoria: str = "",
         es_investigador: bool = False, es_admin: bool = False, invitar: bool = False, fecha_ingreso: str = "",
         fecha_termino: str = "", sin_acceso: bool = False):
    con_vinculo = gestiona_vinculos(auth)
    datos = dict(nombres=nombres.strip(), apellidos=apellidos.strip(),
                 email=email.strip().lower(), es_investigador=es_investigador, es_admin=es_admin,
                 categoria=(categoria or None) if con_vinculo else None,
                 fecha_ingreso=(fecha_ingreso or None) if con_vinculo and categoria else None,
                 fecha_termino=(fecha_termino or None) if con_vinculo and categoria else None)
    errores = []
    try:
        date.fromisoformat(fecha_ingreso) if fecha_ingreso else None
        date.fromisoformat(fecha_termino) if fecha_termino else None
    except ValueError:
        errores.append("Fecha de ingreso o de término no válida.")
    else:
        if datos["categoria"] in vinculos.CATEGORIAS and (e := vinculos.regla_termino(
                datos["categoria"], datos["fecha_ingreso"], datos["fecha_termino"])):
            errores.append(e)
    if not datos["nombres"] or not datos["apellidos"]:
        errores.append("Nombres y apellidos son obligatorios.")
    if not _RE_EMAIL.match(datos["email"]):
        errores.append("Ingrese un correo válido.")
    elif usuarios.por_email(datos["email"]):
        errores.append("Ya existe una cuenta con ese correo.")
    if sin_acceso and es_admin:
        errores.append("Una persona sin acceso no puede tener roles de administración.")
    if datos["categoria"] and datos["categoria"] not in vinculos.CATEGORIAS:
        errores.append("Categoría no válida.")
    if errores:
        return modal("Nuevo usuario", form_usuario({**datos, "invitar": invitar, "sin_acceso": sin_acceso}, errores,
                                                   con_vinculo))

    def tabla():
        """La tabla actualizada (con la persona recién creada), fuera de banda."""
        return Template(cuerpo_tabla(usuarios.listar(), auth, oob=True))
    if sin_acceso:
        u = usuarios.crear(password=None, **datos)
        auditar(auth["id"], "crear_usuario", "usuario", u["id"], f"{datos['email']} (sin acceso)")
        return (modal("Persona registrada",
                      P(f"{u['nombres']} {u['apellidos']} quedó registrada sin acceso al sistema. Para darle acceso, "
                        "use «Habilitar acceso» en su fila."),
                      Div(Button("Listo", cls=ButtonT.primary, data_accion="cerrar-modal", type="button"),
                          cls="flex justify-end mt-4")),
                tabla())
    if invitar:
        # Contraseña aleatoria que nadie conoce: la persona define la suya con el enlace.
        u = usuarios.crear(password=secrets.token_urlsafe(24), debe_cambiar_pass=False, **datos)
        auditar(auth["id"], "crear_usuario", "usuario", u["id"], f"{datos['email']} (invitación)")
        enviar_invitacion(u)
        return (modal("Invitación enviada",
                      P(f"Enviamos a {u['email']} un enlace para que {u['nombres']} defina su contraseña. "
                        "Vale 3 días; si vence, use «Restablecer» o pídale que use «¿Olvidó su contraseña?»."),
                      Div(Button("Listo", cls=ButtonT.primary, data_accion="cerrar-modal", type="button"),
                          cls="flex justify-end mt-4")),
                tabla())
    password = password_temporal()
    u = usuarios.crear(password=password, **datos)
    auditar(auth["id"], "crear_usuario", "usuario", u["id"], datos["email"])
    return (modal_credenciales("Cuenta creada", u, password,
                               "Entréguela al usuario por un canal seguro. No se volverá a mostrar."),
            # Los elementos de tabla OOB deben ir en <template>: sueltos, el parser HTML los descarta.
            tabla())


def modal_desactivar(u, errores=(), termina="si", fecha="", motivo=""):
    v = vinculos.vigente(u["id"])
    return modal(
        "Desactivar cuenta",
        Form(mensaje_error(*errores),
             P(f"{u['nombres']} {u['apellidos']} no podrá ingresar hasta que se reactive la cuenta. Su vínculo "
               f"({vinculos.CATEGORIAS[v['categoria']]}, {vinculos.texto_periodo(v)}) está vigente."),
             Div(fh.Label(fh.Input(type="radio", name="termina", value="si", checked=termina == "si", cls="uk-radio"),
                          Span("Terminar también su vínculo el día", cls="text-sm"),
                          Input(type="date", name="fecha", value=fecha or date.today().isoformat(),
                                cls="uk-input w-44 ml-2", aria_label="Fecha de término"),
                          Select(Option("Motivo…", value=""),
                                 *[Option(t, value=k, selected=k == motivo) for k, t in vinculos.MOTIVOS_TERMINO.items()],
                                 name="motivo", cls="uk-select w-44", aria_label="Motivo del término"),
                          cls="flex flex-wrap items-center gap-2"),
                 fh.Label(fh.Input(type="radio", name="termina", value="no", checked=termina == "no", cls="uk-radio"),
                          Span("Solo desactivar la cuenta (el vínculo sigue vigente)", cls="text-sm"),
                          cls="flex items-center gap-2"),
                 cls="space-y-2"),
             P("El vínculo define qué producción cuenta en los informes: lo publicado mientras estuvo vinculado "
               "sigue contando después.", cls=TextPresets.muted_sm),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
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
def post(uid: int, auth, sess, termina: str = "", fecha: str = "", motivo: str = "", activo: str = ""):
    """Activa (activo=1) o desactiva (activo=0) la cuenta. Desactivar sin terminar el vínculo no pide
    confirmación: el aviso ofrece «Deshacer»."""
    u = usuarios.con_perfil(uid)
    if not u or uid == auth["id"]:
        return fila(u, auth) if u else ""
    if activo in ("0", "1") and (activo == "1") == bool(u["activo"]):
        return fila(u, auth)  # ya está así (p. ej., «Deshacer» pulsado dos veces)
    if u["activo"] and termina == "si":
        if not gestiona_vinculos(auth):
            return SIN_PERMISO
        errores = vinculos.terminar(uid, fecha, motivo or None)
        if errores:
            return modal_desactivar(u, errores, termina, fecha, motivo), HtmxResponseHeaders(
                retarget=f"#{ID_MODAL}", reswap="innerHTML")
        auditar(auth["id"], "terminar_vinculo", "investigador", uid,
                fecha + (f" ({vinculos.MOTIVOS_TERMINO[motivo].lower()})" if motivo else ""))
    usuarios.set_activo(uid, not u["activo"])
    auditar(auth["id"], "desactivar_usuario" if u["activo"] else "activar_usuario", "usuario", uid)
    if u["activo"] and termina != "si":
        aviso_con_deshacer(sess, f"Cuenta de {u['nombres']} {u['apellidos']} desactivada: no podrá ingresar.",
                           hx_post=f"{BASE}/{uid}/activo", hx_vals='{"activo": "1"}', hx_target=f"#usuario-{uid}",
                           hx_swap="outerHTML")
    return fila(usuarios.con_perfil(uid), auth), Div(id=ID_MODAL, hx_swap_oob="true")


@rt(BASE + "/{uid}/categoria")
def post(uid: int, auth, sess, categoria: str = ""):
    u = usuarios.con_perfil(uid)
    if not u or not u["es_investigador"]:
        return ""
    if categoria and categoria not in vinculos.CATEGORIAS:
        return Response("Categoría no válida", status_code=400)
    if not gestiona_vinculos(auth):
        return SIN_PERMISO
    vinculos.corregir_categoria_vigente(uid, categoria or None)
    auditar(auth["id"], "cambiar_categoria", "investigador", uid,
            f"{vinculos.categoria_texto(u['categoria'])} → {vinculos.categoria_texto(categoria)}")
    add_toast(sess, f"{u['nombres']} {u['apellidos']}: {vinculos.categoria_texto(categoria)}.", "success")
    return fila(usuarios.con_perfil(uid), auth)


@rt(BASE + "/{uid}/desbloquear")
def post(uid: int, auth, sess):
    u = usuarios.con_perfil(uid)
    if not u:
        return ""
    usuarios.desbloquear(u["email"])
    auditar(auth["id"], "desbloquear_usuario", "usuario", uid)
    add_toast(sess, f"Cuenta de {u['nombres']} {u['apellidos']} desbloqueada. Su contraseña no cambió.", "success")
    return fila(u, auth)


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
            Template(fila(u, auth)(hx_swap_oob="true")))
