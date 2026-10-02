"""BibTeX: importar productos (con vista previa) y exportar «Mis productos» o el CV.

Las URL de descarga no terminan en .bib: la ruta de archivos estáticos de FastHTML capturaría
cualquier URL con extensión conocida. El nombre del archivo lo da Content-Disposition.
"""
import base64

from fasthtml.common import (A, APIRouter, Code, Div, HtmxResponseHeaders, Input, P, Response, Span,
                             Tbody, Td, Th, Thead, Tr, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import (Button, ButtonT, Form, Label, LabelT, LabelTextArea, Table, TextPresets)

from app.comun import permisos
from app.investigacion import bibtex, productos
from app.acreditacion import informes
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.db import auditar, sin_tildes

rt = APIRouter()
EVENTO = "productos-cambiados"


def _descarga(texto: str, nombre: str):
    return Response(texto.encode("utf-8"), media_type="application/x-bibtex; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"',
                             "Cache-Control": "private, no-store"})


# --- Exportar ---------------------------------------------------------------------------------------

@rt("/productos/bibtex")
def get(auth, q: str = "", anio: str = "", tipo: str = "", informe: bool = False, area: str = ""):
    """Exporta lo que se ve en «Mis productos» con los filtros vigentes."""
    lista = productos.sin_preprints_publicados(productos.de_investigador(auth["id"], q, anio, tipo, informe, area=area))
    return _descarga(bibtex.exportar(lista), "productos.bib")


@rt("/informes/cv/bibtex")
def get(auth, desde: str = "", hasta: str = "", informe: bool = False, uid: int = None, filiacion: bool = False):
    uid = uid if (uid and permisos.puede(auth, "ver_cv_ajeno")) else auth["id"]
    d, h = informes.periodo_valido(desde, hasta)
    datos = informes.cv(uid, d, h, informe, filiacion)
    if not datos["perfil"]:
        return Response("No encontrado", status_code=404)
    lista = [p for clave, _ in informes.CATEGORIAS for p in datos["grupos"][clave]]
    apellido = sin_tildes(datos["perfil"]["apellidos"]).split()[0] if datos["perfil"]["apellidos"] else "cv"
    return _descarga(bibtex.exportar(lista), f"cv-{apellido}-{d}-{h}.bib")


# --- Importar ------------------------------------------------------------------------------------------

def _form_origen(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Suba su archivo .bib (por ejemplo, el que usa en LaTeX o el que exporta Google Scholar, "
          "MathSciNet o Zotero) o pegue las entradas. Verá una vista previa antes de registrar nada.",
          cls="text-sm"),
        Input(type="file", name="archivo", accept=".bib,.bibtex,text/plain,application/x-bibtex",
              aria_label="Archivo BibTeX"),
        LabelTextArea("…o pegue aquí las entradas", id="texto", rows=6,
                      placeholder="@article{clave,\n  author = {Noether, Emmy},\n  title = {…},\n  …\n}",
                      cls="space-y-2 font-mono text-xs"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
            Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_post="/productos/importar-bibtex/revisar", hx_encoding="multipart/form-data",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


@rt("/productos/importar-bibtex")
def get():
    return modal("Importar desde BibTeX", _form_origen(), ancho="max-w-2xl")


def _estado(x):
    if x["estado"] == "nueva":
        return Label("Nueva", cls=LabelT.primary)
    if x["estado"] == "duplicada":
        return Label("Ya registrada", cls=LabelT.secondary)
    return Label("Error", cls=LabelT.destructive)


def _fila(x, uid):
    d = x["datos"]
    autores = ", ".join(a["apellidos"] for a in x["autores"][:4]) + ("…" if len(x["autores"]) > 4 else "")
    if x["estado"] == "nueva":
        casilla = Input(type="checkbox", name="clave", value=x["clave"], checked=True, cls="uk-checkbox",
                        aria_label=f"Importar {x['clave']}")
        detalle = [Span(a, cls="text-xs text-amber-700 dark:text-amber-400 block") for a in x["avisos"]]
    elif x["estado"] == "duplicada":
        otro = x["existente"]
        ya = productos.es_autor(otro["id"], uid)
        casilla = "" if ya else Input(type="checkbox", name="sumarme", value=str(otro["id"]), cls="uk-checkbox",
                                      aria_label=f"Sumarme como autor de {otro['titulo']}")
        detalle = [Span("Usted ya figura como autor(a)." if ya else
                        "Marque la casilla para sumarse como autor(a) del registro existente.",
                        cls="text-xs block"),
                   A("Ver registro", href=f"/productos/{otro['id']}", target="_blank",
                     cls="text-xs text-primary hover:underline")]
    else:
        casilla = ""
        detalle = [Span(e, cls="text-xs text-red-600 block") for e in x["errores"]]
    tipo = productos.tipo(d["tipo_id"])["nombre"] if d.get("tipo_id") else f"@{x['tipo_bib']}"
    return Tr(Td(casilla), Td(Code(x["clave"], cls="text-xs")),
              Td(Div(d.get("titulo") or "—", cls="font-medium text-sm"),
                 Div(f"{autores} · {d.get('anio') or '¿año?'} · {tipo}", cls=TextPresets.muted_sm)),
              Td(_estado(x), *detalle))


@rt("/productos/importar-bibtex/revisar")
async def post(auth, archivo: UploadFile = None, texto: str = ""):
    contenido = texto
    if archivo is not None and archivo.filename:
        crudo = await archivo.read(bibtex.MAX_BYTES + 1)
        try:
            contenido = crudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            contenido = crudo.decode("latin-1")
    if not contenido.strip():
        return modal("Importar desde BibTeX", _form_origen(["Suba un archivo o pegue entradas BibTeX."]),
                     ancho="max-w-2xl")
    entradas, generales = bibtex.leer(contenido)
    if not entradas:
        return modal("Importar desde BibTeX", _form_origen(generales), ancho="max-w-2xl")
    cuenta = {k: sum(x["estado"] == k for x in entradas) for k in ("nueva", "duplicada", "error")}
    return modal(
        "Vista previa de la importación",
        mensaje_error(*generales),
        P(f"{cuenta['nueva']} nueva(s) · {cuenta['duplicada']} ya registrada(s) · {cuenta['error']} con error.",
          cls="text-sm font-medium mb-1"),
        P("Los coautores del instituto se reconocen por nombre; los externos nuevos se registran al confirmar.",
          cls=(TextPresets.muted_sm, "mb-3")),
        Form(
            Input(type="hidden", name="contenido", value=base64.b64encode(contenido.encode()).decode()),
            Div(Table(Thead(Tr(Th(""), Th("Clave"), Th("Entrada"), Th("Estado"))),
                      Tbody(*[_fila(x, auth["id"]) for x in entradas]),
                      cls="uk-table-divider uk-table-small uk-table-middle"),
                cls="max-h-[50vh] overflow-y-auto border border-border rounded-md"),
            Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                Button("Importar lo marcado", type="submit", cls=ButtonT.primary,
                       disabled=not (cuenta["nueva"] or cuenta["duplicada"])),
                cls="flex justify-end gap-2 mt-4"),
            hx_post="/productos/importar-bibtex/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-5xl")


@rt("/productos/importar-bibtex/confirmar")
def post(auth, sess, contenido: str = "", clave: list[str] = None, sumarme: list[int] = None):
    try:
        texto = base64.b64decode(contenido, validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        return modal("Importar desde BibTeX", _form_origen(["No se pudo leer el contenido. Súbalo otra vez."]))
    entradas, _ = bibtex.leer(texto)
    creados = bibtex.crear(entradas, set(clave or []), auth["id"])
    # Solo se permite sumarse a registros que la vista previa marcó como duplicados de este archivo.
    duplicados = {x["existente"]["id"] for x in entradas if x["estado"] == "duplicada"}
    sumado = [pid for pid in (sumarme or []) if pid in duplicados and not productos.es_autor(pid, auth["id"])]
    for pid in sumado:
        productos.sumar_autor(pid, auth["id"])
    if creados or sumado:
        auditar(auth["id"], "importar_bibtex", "producto", None,
                f"{len(creados)} creado(s), autor(a) en {len(sumado)} existente(s)")
    add_toast(sess, f"Importación lista: {len(creados)} producto(s) nuevo(s)"
                    + (f", y ahora figura como autor(a) en {len(sumado)} existente(s)." if sumado else "."),
              "success")
    return "", HtmxResponseHeaders(trigger=EVENTO)
