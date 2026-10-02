"""Carga masiva de cuentas desde un CSV: plantilla, vista previa y confirmación."""
import base64

from fasthtml.common import A, APIRouter, Code, Div, P, Response, Span, Template, Thead, Tr, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import (Button, ButtonT, Form, Input, Label, LabelCheckboxX, LabelT, Table, Tbody, Td, Th,
                           TextPresets, UkIcon)

from app.comun import config, importar_usuarios, usuarios, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.rutas.admin_usuarios.comun import BASE, cuerpo_tabla, gestiona_vinculos
from app.comun.rutas.admin_usuarios.cuentas import enviar_invitacion

rt = APIRouter()


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
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
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
            Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
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
                   cls=(ButtonT.default, "mt-3"), data_accion="copiar", data_copiar=credenciales,
                   data_copiado="Copiado"))
    return (modal("Importación terminada", cuerpo,
                  Div(Button("Listo", cls=ButtonT.primary, data_accion="cerrar-modal", type="button"),
                      cls="flex justify-end mt-4"), ancho="max-w-2xl"),
            tabla)
