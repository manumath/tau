"""Piezas compartidas por las pantallas de usuarios: la fila de cada persona (con sus etiquetas,
estado y botones) y el permiso de la Dirección de Carrera sobre categorías y vínculos."""
import fasthtml.common as fh
from fasthtml.common import Div, Option, Response, Span, Tr
from monsterui.all import Button, ButtonT, Label, LabelT, Tbody, Td, TextPresets, UkIcon

from app.comun import academicos, config, permisos, usuarios, vinculos
from app.comun.componentes.layout import ID_MODAL
from app.comun.componentes.registros import fecha_local

BASE = "/admin/usuarios"
ID_TBODY = "tabla-usuarios"
SIN_PERMISO = Response("Solo la Dirección de Carrera define la categoría y el vínculo.", status_code=403)


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
