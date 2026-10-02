"""Historial de vínculos desde Recursos Humanos (CSV): plantilla, vista previa y confirmación."""
import base64

from fasthtml.common import A, APIRouter, Code, Div, P, Response, Span, Template, Thead, Tr, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Form, Input, Label, LabelT, Table, Tbody, Td, Th, TextPresets, UkIcon

from app.comun import importar_vinculos, usuarios, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.rutas.admin_usuarios.comun import BASE, cuerpo_tabla

rt = APIRouter()


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
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
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
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
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
                  Div(Button("Listo", cls=ButtonT.primary, data_accion="cerrar-modal", type="button"),
                      cls="flex justify-end mt-4")),
            Template(cuerpo_tabla(usuarios.listar(), auth, oob=True)))
