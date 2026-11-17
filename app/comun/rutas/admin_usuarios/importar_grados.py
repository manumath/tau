"""Grados académicos desde CSV (PLAN §61): plantilla, vista previa y confirmación. Los carga quien gestiona las fichas
académicas; la carga solo agrega grados."""
import base64

from fasthtml.common import A, APIRouter, Code, Div, P, Response, Span, Thead, Tr, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Form, Input, Label, LabelT, Table, Tbody, Td, Th, TextPresets, UkIcon

from app.comun import academicos, importar_grados
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.rutas.admin_usuarios.comun import BASE

rt = APIRouter()
TITULO = "Importar grados académicos"


def _form(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Suba un CSV con una fila por grado: ", Code("email"), ", ", Code("nivel"), " (licenciatura, maestría, "
          "doctorado…) y, si los tiene, ", Code("titulo"), ", ", Code("institucion"), ", ", Code("pais"), " y ",
          Code("anio"), ".", cls="text-sm"),
        P("La carga solo agrega: no borra grados y omite los que ya están registrados. Primero verá una vista previa.",
          cls=TextPresets.muted_sm),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{BASE}/importar-grados/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
            Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_post=f"{BASE}/importar-grados/revisar", hx_encoding="multipart/form-data",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


@rt(f"{BASE}/importar-grados")
def get():
    return modal(TITULO, _form(), ancho="max-w-2xl")


@rt(f"{BASE}/importar-grados/plantilla")
def get():
    return Response(importar_grados.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-grados.csv"'})


@rt(f"{BASE}/importar-grados/revisar")
async def post(archivo: UploadFile = None):
    if archivo is None or not archivo.filename:
        return modal(TITULO, _form(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar_grados.MAX_BYTES + 1)
    personas, errores = importar_grados.leer(contenido)
    if not personas:
        return modal(TITULO, _form(errores), ancho="max-w-2xl")
    nuevos = sum(len(p["grados"]) for p in personas if not p["errores"])
    filas = []
    for p in personas:
        u = p["usuario"]
        nombre = f"{u['apellidos']}, {u['nombres']}" if u else p["email"]
        grados = Div(*[P(academicos.texto_grado(g), cls="text-sm") for g in p["grados"]]) if p["grados"] else "—"
        resultado = (Div(Label("Error", cls=LabelT.destructive), *[P(e, cls="text-sm") for e in p["errores"]])
                     if p["errores"] else
                     Span(f"{len(p['grados'])} nuevo(s)" + (f" · {p['repetidos']} ya registrado(s)" if p["repetidos"]
                                                           else ""), cls="text-sm"))
        filas.append(Tr(Td(Div(nombre, cls="font-medium"), Div(p["email"], cls=TextPresets.muted_sm)), Td(grados),
                        Td(resultado)))
    return modal(
        "Vista previa de los grados",
        P(f"{nuevos} grado(s) nuevo(s) · {sum(1 for p in personas if p['errores'])} persona(s) con errores, se omiten.",
          cls="text-sm font-medium mb-3"),
        Div(Table(Thead(Tr(Th("Persona"), Th("Grados nuevos"), Th("Resultado"))), Tbody(*filas),
                  cls="uk-table-divider uk-table-small"),
            cls="max-h-96 overflow-y-auto border border-border rounded-md mb-4"),
        Form(Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button(f"Agregar {nuevos} grado(s)", type="submit", cls=ButtonT.primary, disabled=not nuevos),
                 cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/importar-grados/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-4xl")


@rt(f"{BASE}/importar-grados/confirmar")
def post(auth, sess, contenido: str = ""):
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return modal(TITULO, _form(["No se pudo leer el archivo. Súbalo otra vez."]))
    personas, _ = importar_grados.leer(datos)
    n = importar_grados.aplicar(personas, auth["id"])
    add_toast(sess, f"Se agregaron {n} grado(s).", "success")
    return modal("Grados importados", P(f"Se agregaron {n} grado(s) académico(s)."),
                 Div(Button("Listo", cls=ButtonT.primary, data_accion="cerrar-modal", type="button"),
                     cls="flex justify-end mt-4"))
