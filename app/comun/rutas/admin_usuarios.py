"""Administración de cuentas: listado con búsqueda en vivo, alta, activación y restablecimiento."""
import base64
import re
import secrets
from datetime import date, datetime, timezone

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Code, Div, HtmxResponseHeaders, Li, Option, P, Response, Select,
                             Span, Template, Thead, Tr, UploadFile, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, H3, Button, ButtonT, Form, FormLabel, Input, Label, LabelCheckboxX, LabelInput, LabelT,
                           Table, Tbody, Td, Th, TextPresets, UkIcon)

from app.comun import (academicos, config, correo, importar_usuarios, importar_vinculos, permisos, tokens,
                       unidades, usuarios, vinculos)
from app.comun.componentes import grados as grados_ui
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
            *[Option(t, value=c, selected=c == actual) for c, t in vinculos.CATEGORIAS.items()]]


def gestiona_vinculos(auth) -> bool:
    """Categoría y vínculo (cambios, término, carga contratada): solo la Dirección de Carrera."""
    return permisos.puede(auth, "gestionar_vinculos", vinculos.carrera())


def resumen_vinculo(u, con_boton=True):
    """Categoría vigente, carga contratada, aviso si falta la fecha de ingreso y botón para abrir el
    historial."""
    v = vinculos.vigente(u["id"])
    if v:
        partes = [Span(vinculos.CATEGORIAS[v["categoria"]], cls="text-sm")]
        if vinculos.carga_de(v):
            partes.append(Span(f" · {v['horas_contratadas']} h/mes", cls=TextPresets.muted_sm))
        if not v["fecha_inicio"]:
            partes.append(Span(" · ingreso sin fecha", cls="text-xs text-amber-700"))
    else:
        partes = [Span("Sin categoría" if not vinculos.listar(u["id"]) else "Sin vínculo vigente",
                       cls="text-sm text-amber-700")]
    return Div(*partes,
               fh.Button(UkIcon("id-card", height=14, width=14), "Vínculo", type="button",
                         cls="inline-flex items-center gap-1 text-xs text-primary hover:underline ml-2",
                         hx_get=f"{BASE}/{u["id"]}/vinculo", hx_target=f"#{ID_MODAL}") if con_boton else "",
               cls="flex flex-wrap items-center")


CORTO = {"administracion_sistema": "Adm. del sistema", "direccion_instituto": "Dir. Instituto",
         "direccion_carrera": "Dir. Carrera", "coordinacion_academica": "Coord. académica",
         "comite_acreditacion": "Comité de acreditación", "gestion_datos": "Gestión de datos"}


def _personal_academico(u) -> bool:
    """Investigadores, docentes y quien tenga vínculos (no las cuentas solo de administración)."""
    return bool(u["es_investigador"] or vinculos.listar(u["id"]) or not permisos.roles_vigentes(u["id"]))


def _etiquetas_perfil(u, gestiona_roles=False, gestiona_vinculos=False):
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
               resumen_vinculo(u, gestiona_vinculos) if _personal_academico(u) else "",
               cls="space-y-1")


def _estado(u, bloqueada=False):
    if not u["activo"]:
        return Label("Inactiva", cls=LabelT.destructive)
    if academicos.sin_acceso(u):
        return Span(UkIcon("user-round-x", height=14, width=14), "Sin acceso",
                    title="Registrada solo por sus datos. Se le da acceso con «Habilitar acceso» (contraseña temporal).",
                    cls="inline-flex items-center gap-1 text-muted-foreground text-sm whitespace-nowrap")
    if bloqueada:
        return Span(UkIcon("lock", height=14, width=14), "Bloqueada por intentos fallidos",
                    title=f"Se desbloquea sola a los {config.LOGIN_VENTANA_MIN} minutos, o con el botón del candado.",
                    cls="inline-flex items-center gap-1 text-red-600 text-sm whitespace-nowrap")
    if u["debe_cambiar_pass"]:
        return Span(UkIcon("clock", height=14, width=14), "Sin primer ingreso",
                    cls="inline-flex items-center gap-1 text-amber-600 text-sm whitespace-nowrap")
    return Span(UkIcon("check", height=14, width=14), "Activa",
                cls="inline-flex items-center gap-1 text-green-600 text-sm")


def fila(u, auth: dict):
    """Fila de una persona. Muestra solo las acciones que quien mira (`auth`) puede hacer."""
    uid = u["id"]
    yo_id = auth["id"]
    es_yo = uid == yo_id
    cuentas = permisos.puede(auth, "administrar_cuentas")
    bloqueada = usuarios.bloqueado(u["email"])
    boton_desbloquear = Button(
        UkIcon("lock-open", height=18, width=18), cls=(ButtonT.ghost, ButtonT.icon),
        aria_label="Desbloquear", title="Desbloquear (sin cambiar la contraseña)",
        hx_post=f"/admin/usuarios/{uid}/desbloquear", hx_target=f"#usuario-{uid}",
        hx_swap="outerHTML") if bloqueada else ""
    # Si tiene vínculo vigente, desactivar abre una ventana que pregunta si también termina.
    con_vinculo = (u["activo"] and u["es_investigador"] and vinculos.vigente(uid)
                   and gestiona_vinculos(auth))
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
    sin_acceso = academicos.sin_acceso(u)
    boton_reset = Button(
        UkIcon("key-round", height=18, width=18),
        cls=(ButtonT.ghost, ButtonT.icon),
        aria_label="Habilitar acceso" if sin_acceso else "Restablecer contraseña",
        hx_post=f"/admin/usuarios/{uid}/restablecer", hx_target=f"#{ID_MODAL}",
        hx_confirm=(f"¿Habilitar el acceso de {u['email']} con una contraseña temporal?" if sin_acceso else
                    f"¿Generar una nueva contraseña temporal para {u['email']}? La actual dejará de funcionar."),
        disabled=es_yo,
        title="Use «Contraseña» en el menú para cambiar la suya" if es_yo else
              ("Habilitar acceso (contraseña temporal)" if sin_acceso else "Restablecer contraseña"))
    boton_ficha = Button(
        UkIcon("graduation-cap", height=18, width=18), cls=(ButtonT.ghost, ButtonT.icon),
        aria_label="Ficha académica", title="Ficha académica (grados)",
        hx_get=f"{BASE}/{uid}/ficha", hx_target=f"#{ID_MODAL}") \
        if permisos.puede(auth, "gestionar_fichas") or permisos.puede(auth, "ver_datos_personales") else ""
    return Tr(
        Td(Div(f"{u['apellidos']}, {u['nombres']}", cls="font-medium"),
           Div("(usted)", cls=TextPresets.muted_sm) if es_yo else ""),
        Td(u["email"]),
        Td(_etiquetas_perfil(u, permisos.puede(auth, "asignar_roles"), gestiona_vinculos(auth))),
        Td(_estado(u, bloqueada)),
        Td(fecha_local(u["ultimo_acceso"]),
           cls=(TextPresets.muted_sm, "whitespace-nowrap hidden lg:table-cell")),
        Td(Div(boton_ficha, *([boton_desbloquear, boton_activo, boton_reset] if cuentas else []),
               cls="flex gap-1 justify-end")),
        id=f"usuario-{uid}")


def cuerpo_tabla(lista, auth, oob=False):
    filas = [fila(u, auth) for u in lista] or [
        Tr(Td("No hay usuarios que coincidan con la búsqueda.", colspan=6,
              cls=(TextPresets.muted_sm, "text-center py-6")))]
    return Tbody(*filas, id=ID_TBODY, hx_swap_oob="true" if oob else None)


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
                  cls="uk-table-middle uk-table-divider uk-table-hover"),
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
                      Div(Button("Listo", cls=ButtonT.primary, onclick=JS_CERRAR, type="button"),
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
                      Div(Button("Listo", cls=ButtonT.primary, onclick=JS_CERRAR, type="button"),
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
def post(uid: int, auth, termina: str = "", fecha: str = "", motivo: str = ""):
    u = usuarios.con_perfil(uid)
    if not u or uid == auth["id"]:
        return fila(u, auth) if u else ""
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


# --- Carga masiva desde CSV ------------------------------------------------------------------

def _form_archivo(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Suba un archivo CSV (se puede exportar desde Excel) con una fila por persona y las columnas ",
          Code("email"), ", ", Code("nombres"), ", ", Code("apellidos"), " y, si quiere, ", Code("categoria"),
          " (titular, contratado, interino, invitado o externo), ", Code("investigador"),
          " y ", Code("admin"), " (sí/no: asigna Administración del sistema y Dirección del Instituto; otros roles, "
          "después en «Roles»). Primero verá una vista previa: no se crea nada hasta confirmar.",
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


def _leer_cuentas(contenido, auth):
    """Lee el CSV de cuentas. La categoría solo la define la Dirección de Carrera: para quien no
    gestiona vínculos, esa columna se ignora (se asigna después en «Vínculo»)."""
    filas, errores = importar_usuarios.leer(contenido)
    if not gestiona_vinculos(auth):
        for f in filas:
            f["categoria"] = None
    return filas, errores


@rt(f"{BASE}/importar/revisar")
async def post(auth, archivo: UploadFile = None):
    if archivo is None or not archivo.filename:
        return modal("Importar cuentas desde CSV", _form_archivo(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar_usuarios.MAX_BYTES + 1)
    filas, errores = _leer_cuentas(contenido, auth)
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
                   Td(vinculos.CATEGORIAS.get(f["categoria"], "—") if f["categoria"] else "—"),
                   Td(_etiqueta_estado(f), Span(f" {f['mensaje']}", cls="text-sm") if f["mensaje"] else ""))
                for f in filas]),
        cls="uk-table-divider uk-table-small")
    return modal(
        "Vista previa de la importación",
        mensaje_error(*errores),
        P(f"{nuevas} cuenta(s) nueva(s) · {existentes} ya existente(s), se omiten · {con_error} con error, se omiten.",
          cls="text-sm font-medium mb-3"),
        "" if gestiona_vinculos(auth) else P("La categoría no se importa: la define la Dirección de Carrera en "
                                             "«Vínculo».", cls=(TextPresets.muted_sm, "mb-3")),
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
    filas, _ = _leer_cuentas(datos, auth)
    creadas = importar_usuarios.crear(filas, invitar, auth["id"], enviar_invitacion)
    tabla = Template(cuerpo_tabla(usuarios.listar(), auth, oob=True))
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
        Template(fila(usuarios.con_perfil(uid), auth)(hx_swap_oob="true")),
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


# --- Ficha académica (grados) -----------------------------------------------------------------------------

def _bloque(id_, *contenido):
    return Div(H3("Grados académicos", cls="text-base font-semibold mb-2"), *contenido, id=id_)


def _grados_ficha(uid, errores=(), datos=None):
    return grados_ui.seccion_grados(uid, f"{BASE}/{uid}/grados", "ficha-grados", _bloque, errores, datos)


def seccion_datos_personales(uid, errores=(), valor=None):
    """Solo para quien puede ver datos personales (Administración del sistema)."""
    fecha = academicos.fecha_nacimiento(uid) if valor is None else valor
    return Div(
        H3("Datos personales", cls="text-base font-semibold mb-2"),
        P("Solo la ven la Administración del sistema y la propia persona (sin editarla). Los informes usan "
          "tramos de edad.", cls=(TextPresets.muted_sm, "mb-2")),
        mensaje_error(*errores),
        Form(Div(LabelInput("Fecha de nacimiento", id="fecha_nacimiento", name="fecha_nacimiento", type="date",
                            value=fecha or ""),
                 Button("Guardar", type="submit", cls=(ButtonT.default, ButtonT.sm, "self-end")),
                 cls="flex flex-wrap gap-3"),
             hx_post=f"{BASE}/{uid}/fecha-nacimiento", hx_target="#ficha-datos-personales", hx_swap="outerHTML"),
        id="ficha-datos-personales", cls="mt-6")


def modal_ficha(u, auth):
    uid = u["id"]
    return modal(
        f"Ficha académica de {u['nombres']} {u['apellidos']}",
        P("Datos de la persona que pide la acreditación (Guía de Antecedentes, hojas 10 y 11). Los investigadores "
          "también pueden completar sus grados en «Mi perfil».", cls=(TextPresets.muted_sm, "mb-3")),
        _grados_ficha(uid) if permisos.puede(auth, "gestionar_fichas") else
        Div(H3("Grados académicos", cls="text-base font-semibold mb-2"),
            Ul(*[Li(academicos.texto_grado(g), cls="text-sm py-1") for g in academicos.grados(uid)])
            if academicos.grados(uid) else P("Sin grados registrados.", cls=TextPresets.muted_sm)),
        seccion_datos_personales(uid) if permisos.puede(auth, "ver_datos_personales") else "",
        Div(Button("Listo", type="button", cls=ButtonT.default, onclick=JS_CERRAR), cls="flex justify-end mt-4"),
        ancho="max-w-3xl")


@rt(BASE + "/{uid}/ficha")
def get(auth, uid: int):
    u = usuarios.con_perfil(uid)
    return modal_ficha(u, auth) if u else Response("No encontrado", status_code=404)


@rt(BASE + "/{uid}/fecha-nacimiento")
def post(auth, sess, uid: int, fecha_nacimiento: str = ""):
    if not permisos.puede(auth, "ver_datos_personales") or not usuarios.por_id(uid):
        return Response("No autorizado", status_code=403)
    antes = academicos.fecha_nacimiento(uid)
    errores = academicos.fijar_fecha_nacimiento(uid, fecha_nacimiento or None, auth["id"])
    if errores:
        return seccion_datos_personales(uid, errores, fecha_nacimiento)
    # La auditoría registra el cambio, nunca la fecha.
    detalle = "fecha de nacimiento " + ("borrada" if not fecha_nacimiento else "corregida" if antes else "registrada")
    auditar(auth["id"], "datos_personales", "usuario", uid, detalle)
    add_toast(sess, "Fecha de nacimiento guardada.", "success")
    return seccion_datos_personales(uid)


@rt(BASE + "/{uid}/grados")
def post(auth, uid: int, nivel: str = "", titulo: str = "", institucion: str = "", pais: str = "", anio: str = ""):
    if not permisos.puede(auth, "gestionar_fichas") or not usuarios.por_id(uid):
        return Response("No autorizado", status_code=403)
    datos = dict(nivel=nivel, titulo=titulo, institucion=institucion, pais=pais, anio=anio)
    errores = academicos.agregar_grado(uid, datos)
    if errores:
        return _grados_ficha(uid, errores, datos)
    auditar(auth["id"], "agregar_grado", "usuario", uid, academicos.texto_grado({**datos, "anio": anio or None}))
    return _grados_ficha(uid)


@rt(BASE + "/{uid}/grados/{gid}")
def delete(auth, uid: int, gid: int):
    if not permisos.puede(auth, "gestionar_fichas"):
        return Response("No autorizado", status_code=403)
    g = academicos.quitar_grado(uid, gid)
    if g:
        auditar(auth["id"], "quitar_grado", "usuario", uid, academicos.texto_grado(g))
    return _grados_ficha(uid)


# --- Historial de vínculo ---------------------------------------------------------------------------------

AYUDA_TERMINO = ("Contratados, interinos e invitados: con fecha de término (periodo definido). Titular: sin "
                 "término; si se retira, renuncia o fallece, use «Terminar el vínculo».")


def _campos_periodo(d, con_nota=True, sufijo=""):
    return Div(
        Div(Div(FormLabel("Categoría"), Select(*opciones_categoria(d.get("categoria"), vacia="— Elija —"),
                                               name="categoria", cls="uk-select"), cls="space-y-1"),
            LabelInput("Desde", id=f"desde{sufijo}", name="desde", type="date", value=d.get("desde") or ""),
            LabelInput("Hasta", id=f"hasta{sufijo}", name="hasta", type="date", value=d.get("hasta") or ""),
            LabelInput("Nota", id=f"nota{sufijo}", name="nota", value=d.get("nota") or "",
                       placeholder="Resolución, contrato…") if con_nota else "",
            cls="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end"),
        P(AYUDA_TERMINO, cls=(TextPresets.muted_sm, "mt-1")))


def _campo_motivo(nombre="motivo", actual="", sufijo=""):
    return Div(FormLabel("Motivo", fr=f"{nombre}{sufijo}"),
               Select(Option("— Elija —", value=""),
                      *[Option(t, value=k, selected=k == actual) for k, t in vinculos.MOTIVOS_TERMINO.items()],
                      name=nombre, id=f"{nombre}{sufijo}", cls="uk-select", required=True),
               cls="space-y-1")


CAMPOS_CARGA = ("horas", *vinculos.ACTIVIDADES, "carga_detalle")


def _datos_carga(v) -> dict:
    """Valores del formulario a partir de un periodo (o {} si no tiene carga)."""
    c = vinculos.carga_de(v)
    if not c:
        return {}
    return {"horas": str(c["horas"]), **{k: str(h) for k, h in c["actividades"].items()},
            "carga_detalle": c["detalle"] or ""}


def _campos_carga(d, sufijo=""):
    """Carga contratada y su distribución por actividad (solo en el vínculo con la Carrera)."""
    def horas(nombre, etiqueta, opciones, vacia):
        actual = str(d.get(nombre) or "")
        return Div(FormLabel(etiqueta, fr=f"{nombre}{sufijo}"),
                   Select(Option(vacia, value=""),
                          *[Option(f"{h} h/mes", value=str(h), selected=str(h) == actual) for h in opciones],
                          name=nombre, id=f"{nombre}{sufijo}", cls="uk-select"), cls="space-y-1")
    return fh.Fieldset(
        fh.Legend("Carga horaria contratada", cls="text-sm font-medium px-1"),
        P("Total contratado y su distribución por actividad, en múltiplos de 32 h/mes; la distribución debe sumar "
          "el total (por ejemplo, 160 = docencia 64 + investigación 64 + extensión 32). Cada materia asignada como "
          "titular son 32 h/mes de docencia. Déjelo en blanco en periodos sin carga registrada.",
          cls=(TextPresets.muted_sm, "mb-2")),
        Div(horas("horas", "Total contratado", vinculos.CARGAS, "— Sin registrar —"),
            *[horas(k, t, vinculos.CARGAS, "0") for k, t in vinculos.ACTIVIDADES.items()],
            cls="grid grid-cols-2 sm:grid-cols-3 gap-3 items-end"),
        LabelInput("Detalle", id=f"carga_detalle{sufijo}", name="carga_detalle", value=d.get("carga_detalle") or "",
                   placeholder="Proyecto, cargo de gestión, programa de extensión…", cls="mt-3"),
        cls="rounded-md border border-border p-3 mt-3")


def modal_vinculo(u, auth, errores=(), editar=None, datos=None):
    """Historial de periodos de vínculo y acciones: cambio de categoría o de carga, término, periodo
    histórico, corrección. Solo para quien gestiona los vínculos (la Dirección de Carrera)."""
    uid = u["id"]
    datos = datos or {}
    periodos = vinculos.listar(uid)
    vig = vinculos.vigente(uid)
    filas = []
    for v in periodos:
        if editar == v["id"]:
            filas.append(Tr(Td(Form(
                _campos_periodo({"categoria": v["categoria"], "desde": v["fecha_inicio"], "hasta": v["fecha_fin"],
                                 "jornada": v["jornada_horas"], "nota": v["nota"], **datos}, sufijo=f"-{v["id"]}"),
                _campos_carga(datos or _datos_carga(v), sufijo=f"-{v["id"]}"),
                Div(Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                           hx_get=f"{BASE}/{uid}/vinculo", hx_target=f"#{ID_MODAL}"),
                    Button("Guardar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                    cls="flex justify-end gap-2 mt-2"),
                hx_put=f"{BASE}/vinculo/{v["id"]}", hx_target=f"#{ID_MODAL}"), colspan=6)))
            continue
        filas.append(Tr(
            Td(vinculos.CATEGORIAS[v["categoria"]], Span(" · vigente", cls="text-xs text-green-700") if vig and v["id"] == vig["id"] else ""),
            Td(v["fecha_inicio"] or Span("sin registrar", cls="text-amber-700"), cls="whitespace-nowrap"),
            Td(v["fecha_fin"] or "—",
               Div(vinculos.MOTIVOS_TERMINO[v["motivo_termino"]], cls=TextPresets.muted_sm) if v["motivo_termino"] else "",
               cls="whitespace-nowrap"),
            Td(Span(vinculos.texto_carga(v) or "—", cls="text-sm")),
            Td(Span(v["nota"] or "—", cls="text-sm"),
               Span(f" · jornada según RR. HH.: {v['jornada_horas']} h/semana", cls=TextPresets.muted_sm)
               if v["jornada_horas"] else ""),
            Td(Div(Button(UkIcon("pencil", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon), aria_label="Corregir",
                          title="Corregir", hx_get=f"{BASE}/vinculo/{v["id"]}/editar", hx_target=f"#{ID_MODAL}"),
                   Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon), aria_label="Eliminar",
                          title="Eliminar (solo para corregir errores)", hx_delete=f"{BASE}/vinculo/{v["id"]}",
                          hx_target=f"#{ID_MODAL}", hx_confirm="¿Eliminar este periodo? Úselo solo para corregir errores."),
                   cls="flex justify-end"))))
    tabla = Table(Thead(Tr(Th("Categoría"), Th("Desde"), Th("Hasta"), Th("Carga (h/mes)"), Th("Nota"), Th(""))),
                  Tbody(*filas) if filas else Tbody(Tr(Td("Sin periodos registrados.", colspan=6,
                                                          cls=TextPresets.muted_sm))),
                  cls="uk-table-divider uk-table-small")

    def accion(titulo, *campos, url, boton):
        return fh.Details(fh.Summary(titulo, cls="cursor-pointer text-sm font-medium text-primary"),
                          Form(*campos,
                               Div(Button(boton, type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                                   cls="flex justify-end mt-2"),
                               hx_post=url, hx_target=f"#{ID_MODAL}", cls="mt-2"),
                          cls="rounded-md border border-border p-3")
    acciones = [
        accion("Cambiar de categoría o de carga (ascenso, nuevo contrato)",
               P("Cierra el periodo vigente el día anterior y abre uno nuevo.", cls=TextPresets.muted_sm),
               _campos_periodo(datos or {"categoria": vig["categoria"]}, con_nota=False, sufijo="-cambio"),
               _campos_carga(datos or _datos_carga(vig), sufijo="-cambio"),
               url=f"{BASE}/{uid}/vinculo/cambio", boton="Registrar cambio") if vig else "",
        accion("Terminar el vínculo (fin de contrato, retiro, renuncia, despido, fallecimiento)",
               Div(LabelInput("Último día", id="fecha-termino", name="fecha", type="date",
                              value=date.today().isoformat()),
                   _campo_motivo(sufijo="-termino"), cls="grid grid-cols-2 gap-3 items-end"),
               url=f"{BASE}/{uid}/vinculo/termino", boton="Terminar") if vig else "",
        accion("Agregar un periodo (histórico o nuevo ingreso)",
               _campos_periodo(datos, sufijo="-nuevo"), _campos_carga(datos, sufijo="-nuevo"),
               url=f"{BASE}/{uid}/vinculo/periodo", boton="Agregar"),
    ]
    return modal(
        f"Vínculo de {u['nombres']} {u['apellidos']}",
        mensaje_error(*errores),
        P("Periodos de vínculo con la Carrera de Matemática (el Instituto forma parte de ella: es una sola "
          "dependencia), con su categoría y su carga horaria contratada. Lo define la Dirección de Carrera. La "
          "categoría a la fecha de cada producto o actividad es la que cuenta en los informes. Para cargar el "
          "historial de muchas personas, use «Importar historial» en el listado.",
          cls=(TextPresets.muted_sm, "mb-3")),
        Div(tabla, cls="overflow-x-auto mb-4"),
        Div(*acciones, cls="space-y-2"),
        Div(Button("Listo", type="button", cls=ButtonT.default, onclick=JS_CERRAR), cls="flex justify-end mt-4"),
        Template(fila(usuarios.con_perfil(uid), auth)(hx_swap_oob="true")),
        ancho="max-w-4xl")


def _investigador(uid):
    """La persona (con o sin perfil de investigación: los docentes también tienen vínculo)."""
    return usuarios.con_perfil(uid)


SIN_PERMISO = Response("Solo la Dirección de Carrera define la categoría y el vínculo.", status_code=403)


def _form_carga(req_form) -> dict:
    return {k: req_form.get(k, "") for k in CAMPOS_CARGA}


@rt(BASE + "/{uid}/vinculo")
def get(auth, uid: int):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    return modal_vinculo(u, auth) if gestiona_vinculos(auth) else SIN_PERMISO


@rt(BASE + "/{uid}/vinculo/cambio")
async def post(auth, req, uid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return SIN_PERMISO
    fc = _form_carga(await req.form())
    carga = vinculos.leer_carga(fc)
    errores = vinculos.cambiar_categoria(uid, categoria, desde, jornada or None, auth["id"], carga=carga,
                                         hasta=hasta or None)
    if not errores:
        auditar(auth["id"], "cambiar_categoria", "investigador", uid, f"{categoria} desde {desde}"
                + (f"; carga {vinculos.texto_carga(vinculos.vigente(uid, desde))}" if carga else ""))
    return modal_vinculo(u, auth, errores,
                         datos={"categoria": categoria, "desde": desde, "hasta": hasta, "jornada": jornada, **fc}
                         if errores else None)


@rt(BASE + "/{uid}/vinculo/termino")
def post(auth, uid: int, fecha: str = "", motivo: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return SIN_PERMISO
    errores = ["Indique el motivo del término."] if not motivo else vinculos.terminar(uid, fecha, motivo)
    if not errores:
        auditar(auth["id"], "terminar_vinculo", "investigador", uid,
                f"{fecha} ({vinculos.MOTIVOS_TERMINO[motivo].lower()})")
    return modal_vinculo(u, auth, errores)


@rt(BASE + "/{uid}/vinculo/periodo")
async def post(auth, req, uid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = "",
               nota: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return SIN_PERMISO
    fc = _form_carga(await req.form())
    carga = vinculos.leer_carga(fc)
    errores = vinculos.agregar(uid, categoria, desde or None, hasta or None, jornada or None, nota, auth["id"],
                               carga=carga)
    if not errores:
        auditar(auth["id"], "agregar_vinculo", "investigador", uid,
                f"{categoria} {desde or '?'} a {hasta or 'hoy'}" + (f"; carga {carga['horas']} h/mes" if carga else ""))
    datos = dict(categoria=categoria, desde=desde, hasta=hasta, jornada=jornada, nota=nota, **fc) if errores else None
    return modal_vinculo(u, auth, errores, datos=datos)


def _periodo_o_error(vid, auth):
    """(periodo, None) si existe y quien pide gestiona los vínculos; (None, respuesta) si no."""
    v = vinculos.obtener(vid)
    if not v:
        return None, Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return None, SIN_PERMISO
    return v, None


@rt(BASE + "/vinculo/{vid}/editar")
def get(auth, vid: int):
    v, error = _periodo_o_error(vid, auth)
    if error:
        return error
    return modal_vinculo(_investigador(v["usuario_id"]), auth, editar=vid)


@rt(BASE + "/vinculo/{vid}")
async def put(auth, req, vid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = "",
              nota: str = ""):
    v, error = _periodo_o_error(vid, auth)
    if error:
        return error
    fc = _form_carga(await req.form())
    carga = vinculos.leer_carga(fc)
    errores = vinculos.editar(vid, categoria, desde or None, hasta or None, jornada or None, nota, carga=carga)
    if not errores:
        auditar(auth["id"], "corregir_vinculo", "investigador", v["usuario_id"],
                f"{categoria} {desde or '?'} a {hasta or 'hoy'}" + (f"; carga {carga['horas']} h/mes" if carga else ""))
    u = _investigador(v["usuario_id"])
    if errores:
        return modal_vinculo(u, auth, errores, editar=vid,
                             datos=dict(categoria=categoria, desde=desde, hasta=hasta, jornada=jornada, nota=nota, **fc))
    return modal_vinculo(u, auth)


@rt(BASE + "/vinculo/{vid}")
def delete(auth, vid: int):
    v, error = _periodo_o_error(vid, auth)
    if error:
        return error
    vinculos.eliminar(vid)
    auditar(auth["id"], "eliminar_vinculo", "investigador", v["usuario_id"], vinculos.texto_periodo(v))
    return modal_vinculo(_investigador(v["usuario_id"]), auth)


# --- Historial de vínculos desde Recursos Humanos (CSV) -----------------------------------------------------

def _form_historial(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Suba un CSV de Recursos Humanos con una fila por periodo: ", Code("email"), ", ", Code("categoria"), ", ",
          Code("desde"), " y, si quiere, ", Code("hasta"), " (vacío = vigente), ", Code("jornada"), " (horas "
          "semanales) y ", Code("nota"), ". Fechas como AAAA-MM-DD o DD/MM/AAAA.", cls="text-sm"),
        P("El historial de cada persona del archivo se reemplaza por el del archivo; lo demás no cambia. La carga "
          "horaria contratada se registra después en el vínculo de cada persona. Primero verá una vista previa.",
          cls=TextPresets.muted_sm),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href="/admin/usuarios/historial/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
            Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_post="/admin/usuarios/historial/revisar", hx_encoding="multipart/form-data",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


def _leer_historial(contenido, auth):
    return importar_vinculos.leer(contenido)


@rt(f"{BASE}/historial")
def get():
    return modal("Importar historial de vínculos", _form_historial(), ancho="max-w-2xl")


@rt(f"{BASE}/historial/plantilla")
def get():
    return Response(importar_vinculos.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-historial.csv"'})


@rt(f"{BASE}/historial/revisar")
async def post(auth, archivo: UploadFile = None):
    if archivo is None or not archivo.filename:
        return modal("Importar historial de vínculos", _form_historial(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar_vinculos.MAX_BYTES + 1)
    personas, errores = _leer_historial(contenido, auth)
    if not personas:
        return modal("Importar historial de vínculos", _form_historial(errores), ancho="max-w-2xl")
    listas = [p for p in personas if not p["errores"]]
    filas = []
    for p in personas:
        nombre = f"{p['usuario']['apellidos']}, {p['usuario']['nombres']}" if p["usuario"] else p["email"]
        periodos = "; ".join(f"{vinculos.CATEGORIAS[x['categoria']]} {x['desde']} a {x['hasta'] or 'hoy'}"
                             for x in p["periodos"])
        filas.append(Tr(Td(Div(nombre, cls="font-medium"), Div(p["email"], cls=TextPresets.muted_sm)),
                        Td(periodos or "—", cls="text-sm"),
                        Td(Label("Error", cls=LabelT.destructive), Div(*[P(e, cls="text-sm") for e in p["errores"]])
                           if p["errores"] else
                           Span(f"Reemplaza {p['actuales']} periodo(s) actual(es)", cls="text-sm"))))
    return modal(
        "Vista previa del historial",
        P(f"{len(listas)} persona(s) se actualizarán · {len(personas) - len(listas)} con errores, se omiten.",
          cls="text-sm font-medium mb-3"),
        Div(Table(Thead(Tr(Th("Persona"), Th("Periodos del archivo"), Th("Resultado"))), Tbody(*filas),
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
    personas, _ = _leer_historial(datos, auth)
    n = importar_vinculos.aplicar(personas, auth["id"])
    add_toast(sess, f"Historial actualizado para {n} persona(s).", "success")
    return (modal("Historial importado", P(f"Se actualizó el historial de {n} persona(s)."),
                  Div(Button("Listo", cls=ButtonT.primary, onclick=JS_CERRAR, type="button"),
                      cls="flex justify-end mt-4")),
            Template(cuerpo_tabla(usuarios.listar(), auth, oob=True)))
