"""Ficha académica de una persona: grados académicos y fecha de nacimiento (dato personal)."""
from fasthtml.common import APIRouter, Div, Li, P, Response, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H3, Button, ButtonT, Form, LabelInput, TextPresets

from app.comun import academicos, permisos, usuarios
from app.comun.componentes import grados as grados_ui
from app.comun.componentes.layout import mensaje_error, modal
from app.comun.db import auditar
from app.comun.rutas.admin_usuarios.comun import BASE

rt = APIRouter()


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
        Div(Button("Listo", type="button", cls=ButtonT.default, data_accion="cerrar-modal"), cls="flex justify-end mt-4"),
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
