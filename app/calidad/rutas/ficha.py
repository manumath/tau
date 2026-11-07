"""Ficha estadística de la Carrera y exportación por correspondencia (PLAN §57, etapa 7). La ve quien ve el marco de
calidad; la plantilla y la correspondencia que se suben no se guardan."""
from datetime import date

from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Response, Select, Span, Table, Tbody, Td, Th, \
    Thead, Tr, Ul, UploadFile
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, FormLabel, TextPresets, UkIcon

from app.calidad import ficha, marco
from app.calidad.rutas.indicadores import numero
from app.calidad.rutas.informes import XLSX, _archivo, descarga
from app.comun import unidades
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.db import auditar

rt = APIRouter()
BASE = "/calidad/ficha"
MAX_ARCHIVO = 10 * 1024 * 1024


def _marco_visible(auth):
    m = marco.de_unidad(unidades.id_de("CMAT"))
    return m if marco.puede(auth, "ver_marco_calidad", m) else None


def _hasta(hasta: str) -> int:
    hoy = date.today().year
    return int(hasta) if hasta.isdigit() and 2000 <= int(hasta) <= hoy else hoy


def _v(x):
    return "—" if x is None else numero(x) if isinstance(x, float) else str(x)


def _tabla(titulo, columnas, filas, nota=""):
    """Tabla con los periodos en columnas y una fila por concepto: [(concepto, [valores])]."""
    return Card(
        H3(titulo, cls="text-base font-semibold mb-2"),
        Div(Table(Thead(Tr(Th(""), *[Th(c, cls="text-right whitespace-nowrap") for c in columnas])),
                  Tbody(*[Tr(Td(n), *[Td(_v(x), cls="text-right tabular-nums") for x in vals]) for n, vals in filas]),
                  cls="uk-table uk-table-divider uk-table-small text-sm"), cls="overflow-x-auto"),
        P(nota, cls=(TextPresets.muted_sm, "mt-2")) if nota else "")


@rt(BASE)
def get(auth, hasta: str = ""):
    m = _marco_visible(auth)
    if m is None:
        return Response("No autorizado", status_code=403)
    h = _hasta(hasta)
    d = ficha.datos(m, h)
    hoy = date.today().year
    acad = d["academicos"]
    cats = sorted({c for x in acad for c in x["por_categoria"]})
    tramos = list(acad[0]["tramos"]) if acad else []
    sems = [x["semestre"] for x in d["admision"]]
    return pagina(
        "Ficha estadística",
        Div(Div(H2("Ficha estadística de la Carrera"),
                P(f"{d['anios'][0]}–{d['anios'][-1]} · ventana de evidencia del marco de calidad", cls=TextPresets.muted_sm)),
            Div(Form(Select(*[Option(str(a), value=str(a), selected=a == h) for a in range(hoy, hoy - 15, -1)],
                            name="hasta", aria_label="Hasta el año", cls="uk-select uk-form-small w-28"),
                     Button("Ver", type="submit", cls=(ButtonT.default, ButtonT.sm)), method="get", action=BASE,
                     cls="flex gap-2"),
                descarga("XLSX", f"{BASE}/xlsx?hasta={h}"),
                A(UkIcon("file-spreadsheet", height=14, width=14), "Llenar una plantilla", href=f"{BASE}/plantilla?hasta={h}",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1"),
                cls="flex flex-wrap items-center gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P("Las cifras que suelen pedir los formularios de antecedentes de un proceso de evaluación, por año o por cohorte "
          "(semestre de ingreso). El año en curso es parcial. El XLSX trae además la hoja «Claves», con el nombre de cada "
          "cifra para llenar una plantilla externa.", cls="text-sm max-w-3xl mb-6"),
        Div(_tabla("Cuerpo académico (al 31 de diciembre de cada año, o a hoy)", d["anios"],
                   [*[(t, [x[k] for x in acad]) for k, t in ficha.CAMPOS_ACADEMICOS.items()],
                    *[(f"Categoría: {c}", [x["por_categoria"].get(c, 0) for x in acad]) for c in cats],
                    *[(f"Edad: {t}", [x["tramos"][t] for x in acad]) for t in tramos]]),
            _tabla("Oferta por semestre", [x["semestre"] for x in d["oferta"]],
                   [("Paralelos", [x["paralelos"] for x in d["oferta"]]),
                    ("Inscripciones", [x["inscripciones"] for x in d["oferta"]])],
                   "Inscripciones: suma de inscritos por paralelo (una persona en dos materias cuenta dos veces)."),
            _tabla("Admisión por cohorte", sems,
                   [*[(t, [x[k] for x in d["admision"]]) for k, t in ficha.CAMPOS_ADMISION.items()],
                    *[(f"Edad al ingresar: {t}", [x["tramos"][t] for x in d["admision"]])
                      for t in (d["admision"][0]["tramos"] if d["admision"] else [])]],
                   "Según la carga del CSV de Seguimiento Académico; sin dato de vía de ingreso cuenta como ordinaria."),
            _tabla("Trayectoria de cada cohorte (a hoy)", sems,
                   [(t, [x[k] for x in d["trayectoria"]]) for k, t in ficha.CAMPOS_COHORTE.items()],
                   "«Matriculados al año» queda vacío hasta que la cohorte cumple un año."),
            cls="space-y-6"),
        usuario=auth)


@rt(f"{BASE}/xlsx")
def get(auth, hasta: str = ""):
    m = _marco_visible(auth)
    if m is None:
        return Response("No autorizado", status_code=403)
    d = ficha.datos(m, _hasta(hasta))
    return _archivo(ficha.a_xlsx(d), f"ficha-estadistica-{d['anios'][0]}-{d['anios'][-1]}.xlsx", XLSX)


def _archivo_subido(nombre, acepta):
    return Input(type="file", id=nombre, name=nombre, accept=acepta, required=True, cls="uk-input text-sm")


def _pagina_plantilla(auth, h, errores=()):
    return pagina(
        "Llenar una plantilla",
        A(UkIcon("arrow-left", height=14, width=14), "Ficha estadística", href=f"{BASE}?hasta={h}",
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        H2("Llenar una plantilla con la ficha"),
        Div(P("Llena las celdas de un formulario XLSX externo (por ejemplo, el de antecedentes de una agencia) con las cifras "
              "de la ficha y del tablero de indicadores. Necesita dos archivos:"),
            Ul(Li(Span("La plantilla", cls="font-medium"), ", tal como la entrega el organismo. Solo se escriben las celdas "
                  "indicadas; sus fórmulas, gráficos, imágenes y estilos quedan como estaban."),
               Li(Span("La correspondencia", cls="font-medium"), ": un CSV con las columnas ",
                  Span("hoja,celda,clave", cls="font-mono"), " que dice en qué celda va cada cifra. Las claves están en la "
                  "hoja «Claves» del XLSX de la ficha (p. ej., ", Span("academicos.total.2025", cls="font-mono"), ", ",
                  Span("admision.mujeres.I-2025", cls="font-mono"), ", ", Span("indicador.D3.2.b.2025", cls="font-mono"),
                  ")."), cls="uk-list uk-list-disc pl-5"),
            P("Ninguno de los dos archivos se guarda en el sistema: la correspondencia con los criterios de un organismo es "
              "privada de la Carrera. Revise siempre el resultado antes de enviarlo."),
            cls="text-sm max-w-3xl space-y-3 my-4"),
        Card(Form(mensaje_error(*errores),
                  Div(Div(FormLabel("Plantilla (XLSX)", fr="plantilla"),
                          Div(_archivo_subido("plantilla", ".xlsx")), cls="space-y-2"),
                      Div(FormLabel("Correspondencia (CSV)", fr="correspondencia"),
                          Div(_archivo_subido("correspondencia", ".csv,text/csv")), cls="space-y-2"),
                      Div(FormLabel("Hasta el año", fr="hasta"),
                          Select(*[Option(str(a), value=str(a), selected=a == h)
                                   for a in range(date.today().year, date.today().year - 15, -1)],
                                 id="hasta", name="hasta", cls="uk-select w-28 block"), cls="flex flex-col gap-2"),
                      cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                  Div(Button(UkIcon("download", height=14, width=14), "Llenar y descargar", type="submit",
                             cls=ButtonT.primary), cls="flex justify-end"),
                  method="post", action=f"{BASE}/plantilla", enctype="multipart/form-data", cls="space-y-4")),
        usuario=auth)


@rt(f"{BASE}/plantilla")
def get(auth, hasta: str = ""):
    if _marco_visible(auth) is None:
        return Response("No autorizado", status_code=403)
    return _pagina_plantilla(auth, _hasta(hasta))


@rt(f"{BASE}/plantilla")
async def post(auth, plantilla: UploadFile = None, correspondencia: UploadFile = None, hasta: str = ""):
    m = _marco_visible(auth)
    if m is None:
        return Response("No autorizado", status_code=403)
    h = _hasta(hasta)
    if not (isinstance(plantilla, UploadFile) and isinstance(correspondencia, UploadFile)):
        return _pagina_plantilla(auth, h, ["Suba la plantilla y la correspondencia."])
    p, c = await plantilla.read(MAX_ARCHIVO + 1), await correspondencia.read(MAX_ARCHIVO + 1)
    if len(p) > MAX_ARCHIVO or len(c) > MAX_ARCHIVO:
        return _pagina_plantilla(auth, h, ["Cada archivo puede pesar hasta 10 MB."])
    filas, errores = ficha.leer_correspondencia(c)
    if not errores and not filas:
        errores = ["La correspondencia no tiene filas."]
    if errores:
        return _pagina_plantilla(auth, h, errores[:20])
    contenido, errores, n = ficha.llenar(p, filas, ficha.valores(ficha.datos(m, h)))
    if errores:
        return _pagina_plantilla(auth, h, errores)
    auditar(auth["id"], "llenar_plantilla_ficha", "marco_calidad", m["id"], f"{len(filas)} celdas, {n} con dato, hasta {h}")
    nombre = (plantilla.filename or "plantilla.xlsx").rsplit("/", 1)[-1].removesuffix(".xlsx")
    return _archivo(contenido, f"{_seguro(nombre)}-llena.xlsx", XLSX)


def _seguro(nombre: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in nombre)[:80] or "plantilla"
