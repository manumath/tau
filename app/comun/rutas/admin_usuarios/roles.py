"""Roles de una cuenta: historial, asignación por unidad y término. Los asigna Administración del
sistema, a pedido de las direcciones."""
from datetime import date

import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Option, P, Response, Select, Span, Template, Thead, Tr
from monsterui.all import Button, ButtonT, Form, FormLabel, LabelInput, Table, Tbody, Td, Th, TextPresets

from app.comun import permisos, unidades, usuarios
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.db import auditar
from app.comun.rutas.admin_usuarios.comun import BASE, fila

rt = APIRouter()


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
        Div(Button("Listo", type="button", cls=ButtonT.default, data_accion="cerrar-modal"), cls="flex justify-end mt-4"),
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
