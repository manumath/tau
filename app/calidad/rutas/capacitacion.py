"""Capacitación del personal (PLAN §57, etapa 8): la registran la Dirección de Carrera y Gestión de datos; la ven quienes
ven el marco de calidad."""
import base64
from datetime import date

from fasthtml.common import (A, APIRouter, Code, Div, Option, P, Redirect, Response, Select, Span, Table, Tbody, Td, Th,
                             Thead, Tr, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, Form, Input, Label, LabelInput, LabelT, TextPresets, UkIcon

from app.calidad import capacitacion, evidencias, importar_capacitacion, marco
from app.calidad.rutas.mejora import _botones_modal, _fecha, _select
from app.comun import unidades
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.db import auditar

rt = APIRouter()
BASE = "/calidad/capacitacion"


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _no():
    return Response("No autorizado", status_code=403)


def _registra(auth, m):
    return marco.puede(auth, "registrar_capacitacion", m)


@rt(BASE)
def get(auth, anio: str = ""):
    m = _marco()
    if not marco.puede(auth, "ver_marco_calidad", m):
        return _no()
    hoy = date.today().year
    a = int(anio) if anio.isdigit() and 2000 <= int(anio) <= hoy else hoy
    r = capacitacion.resumen(a)
    lista = capacitacion.listar(a)
    registra = _registra(auth, m)
    return pagina(
        "Capacitación",
        Div(Div(H2("Capacitación del personal"), P(f"Año {a}", cls=TextPresets.muted_sm)),
            Div(Form(Select(*[Option(str(x), value=str(x), selected=x == a) for x in range(hoy, hoy - 15, -1)],
                            name="anio", aria_label="Año", cls="uk-select uk-form-small w-28"),
                     Button("Ver", type="submit", cls=(ButtonT.default, ButtonT.sm)), method="get", action=BASE,
                     cls="flex gap-2"),
                Button(UkIcon("file-up", height=14, width=14), "Importar CSV", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"{BASE}/importar", hx_target=f"#{ID_MODAL}") if registra else "",
                Button(UkIcon("plus", height=14, width=14), "Registrar capacitación", cls=(ButtonT.primary, ButtonT.sm),
                       hx_get=f"{BASE}/nueva", hx_target=f"#{ID_MODAL}") if registra else "",
                cls="flex flex-wrap items-center gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P("Cursos, talleres, diplomados y pasantías de formación que concluyó el personal académico de la Carrera. Cada uno "
          "cuenta en el año en que concluyó. Alimenta el indicador «Personal capacitado».", cls="text-sm max-w-3xl mb-4"),
        Div(*[Card(Div(str(v), cls="text-2xl font-semibold"), Div(t, cls=TextPresets.muted_sm), cls="text-center")
              for v, t in ((f"{r['capacitados']} de {r['vinculados']}", "académicos vinculados se capacitaron"),
                           (r["cursos"], "capacitaciones"), (r["horas"], "horas en total"))],
            cls="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6"),
        Div(Table(Thead(Tr(Th("Persona", cls="w-48"), Th("Capacitación"), Th("Área", cls="w-40"), Th("Horas", cls="w-16 text-right"),
                           Th("Concluyó", cls="w-24"), Th("", cls="w-24"))),
                  Tbody(*[Tr(Td(f"{c['apellidos']}, {c['nombres']}"),
                             Td(Div(c["titulo"], cls="font-medium"), Div(c["institucion"] or "", cls=TextPresets.muted_sm),
                                A(UkIcon("folder-open", height=12, width=12), f" {c['evidencia_titulo']}",
                                  href=f"/calidad/evidencias/{c['evidencia_id']}", cls="text-xs text-primary hover:underline")
                                if c["evidencia_id"] else ""),
                             Td(capacitacion.AREAS[c["area"]]), Td(str(c["horas"] or "—"), cls="text-right"),
                             Td(_fecha(c["fecha_fin"])),
                             Td(Div(Button(UkIcon("pencil", height=12, width=12), cls=(ButtonT.ghost, ButtonT.xs),
                                           aria_label="Editar", title="Editar", hx_get=f"{BASE}/{c['id']}/editar",
                                           hx_target=f"#{ID_MODAL}"),
                                    Button(UkIcon("trash-2", height=12, width=12), cls=(ButtonT.ghost, ButtonT.xs),
                                           aria_label="Quitar", title="Quitar", hx_delete=f"{BASE}/{c['id']}",
                                           hx_target="body", hx_confirm="¿Quitar esta capacitación?"),
                                    cls="flex justify-end") if registra else ""))
                          for c in lista]),
                  cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[48rem]"), cls="overflow-x-auto")
        if lista else P(Span(f"No hay capacitaciones concluidas en {a}."), cls=TextPresets.muted_sm),
        usuario=auth)


def _form(m, d, url, metodo, errores=()):
    def v(k):
        return d.get(k) if d.get(k) is not None else ""
    gente = [(p["id"], f"{p['apellidos']}, {p['nombres']}") for p in capacitacion.personas()]
    evs = [(e["id"], e["titulo"]) for e in evidencias.listar(m["id"])]
    return modal(
        "Capacitación",
        Form(mensaje_error(*errores),
             _select("Persona", "usuario_id", gente, v("usuario_id"), "—"),
             LabelInput("Capacitación", id="titulo", value=v("titulo"), required=True, maxlength=300),
             Div(LabelInput("Institución que la dictó (opcional)", id="institucion", value=v("institucion"), maxlength=300),
                 _select("Área", "area", list(capacitacion.AREAS.items()), v("area") or "disciplinar"),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             Div(LabelInput("Inicio", id="fecha_inicio", type="date", value=v("fecha_inicio"), required=True),
                 LabelInput("Concluyó", id="fecha_fin", type="date", value=v("fecha_fin"), required=True),
                 LabelInput("Horas (opcional)", id="horas", type="number", min=1, max=2000, value=v("horas")),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
             _select("Certificado (evidencia del repositorio, opcional)", "evidencia_id", evs, v("evidencia_id"), "—"),
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-2xl")


def _datos(f):
    return {k: f.get(k, "") for k in capacitacion.CAMPOS}


def _validos(m):
    return {e["id"] for e in evidencias.listar(m["id"])}


@rt(f"{BASE}/nueva")
def get(auth):
    m = _marco()
    return _form(m, {}, BASE, "post") if _registra(auth, m) else _no()


@rt(BASE)
async def post(auth, sess, req):
    m = _marco()
    if not _registra(auth, m):
        return _no()
    x, errores = capacitacion.validar(_datos(await req.form()), _validos(m))
    if errores:
        return _form(m, x, BASE, "post", errores)
    cid = capacitacion.crear(x, auth["id"])
    auditar(auth["id"], "registrar_capacitacion", "capacitacion", cid, x["titulo"])
    add_toast(sess, "Capacitación registrada.", "success")
    return Redirect(f"{BASE}?anio={x['fecha_fin'][:4]}")


@rt(f"{BASE}/{{cid}}/editar")
def get(auth, cid: int):
    m, c = _marco(), capacitacion.obtener(cid)
    if not _registra(auth, m):
        return _no()
    return _form(m, c, f"{BASE}/{cid}", "put") if c else Response("No encontrada", status_code=404)


@rt(f"{BASE}/{{cid}}")
async def put(auth, sess, req, cid: int):
    m, c = _marco(), capacitacion.obtener(cid)
    if not _registra(auth, m):
        return _no()
    if c is None:
        return Response("No encontrada", status_code=404)
    x, errores = capacitacion.validar(_datos(await req.form()), _validos(m))
    if errores:
        return _form(m, x, f"{BASE}/{cid}", "put", errores)
    capacitacion.actualizar(cid, x)
    auditar(auth["id"], "editar_capacitacion", "capacitacion", cid, x["titulo"])
    add_toast(sess, "Capacitación guardada.", "success")
    return Redirect(f"{BASE}?anio={x['fecha_fin'][:4]}")


@rt(f"{BASE}/{{cid}}")
def delete(auth, sess, cid: int):
    m, c = _marco(), capacitacion.obtener(cid)
    if not _registra(auth, m):
        return _no()
    if c is None:
        return Response("No encontrada", status_code=404)
    capacitacion.eliminar(cid)
    auditar(auth["id"], "quitar_capacitacion", "capacitacion", cid, c["titulo"])
    add_toast(sess, "Capacitación quitada.", "success")
    return Redirect(f"{BASE}?anio={c['fecha_fin'][:4]}")


# --- Carga por CSV (PLAN §61) -------------------------------------------------------------------------------

def _form_importar(errores=()):
    return modal(
        "Importar capacitaciones",
        Form(mensaje_error(*errores),
             P("Suba un CSV con una fila por persona y capacitación: ", Code("email"), ", ", Code("titulo"), ", ",
               Code("area"), " (disciplinar, pedagógica, investigación, gestión, IA u otra) y, si los tiene, ",
               Code("institucion"), ", ", Code("horas"), ", ", Code("fecha_inicio"), " y ", Code("fecha_fin"), ".",
               cls="text-sm"),
             P("Si solo conoce el año, use la columna ", Code("anio"), ": la capacitación se registra como concluida el "
               "31 de diciembre de ese año. Lo que ya está registrado se omite. Primero verá una vista previa.",
               cls=TextPresets.muted_sm),
             A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{BASE}/importar/plantilla",
               cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
             Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/importar/revisar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}",
             cls="space-y-4"),
        ancho="max-w-2xl")


@rt(f"{BASE}/importar")
def get(auth):
    return _form_importar() if _registra(auth, _marco()) else _no()


@rt(f"{BASE}/importar/plantilla")
def get(auth):
    if not _registra(auth, _marco()):
        return _no()
    return Response(importar_capacitacion.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-capacitacion.csv"'})


@rt(f"{BASE}/importar/revisar")
async def post(auth, archivo: UploadFile = None):
    if not _registra(auth, _marco()):
        return _no()
    if archivo is None or not archivo.filename:
        return _form_importar(["Seleccione un archivo."])
    contenido = await archivo.read(importar_capacitacion.MAX_BYTES + 1)
    filas, errores = importar_capacitacion.leer(contenido)
    if not filas:
        return _form_importar(errores)
    nuevas = sum(f["estado"] == "nueva" for f in filas)
    insignias = {"nueva": ("Nueva", LabelT.primary), "existe": ("Ya registrada", LabelT.secondary),
                 "error": ("Error", LabelT.destructive)}
    return modal(
        "Vista previa de las capacitaciones",
        P(f"{nuevas} nueva(s) · {sum(f['estado'] == 'existe' for f in filas)} ya registrada(s) · "
          f"{sum(f['estado'] == 'error' for f in filas)} con errores, se omiten.", cls="text-sm font-medium mb-3"),
        Div(Table(Thead(Tr(Th("Fila", cls="w-12"), Th("Persona"), Th("Capacitación"), Th("Concluyó", cls="w-24"),
                           Th("Resultado"))),
                  Tbody(*[Tr(Td(str(f["linea"])), Td(f["nombre"] or f["email"]), Td(f["titulo"]),
                             Td(_fecha(f["datos"]["fecha_fin"]) if f["datos"] else "—"),
                             Td(Label(insignias[f["estado"]][0], cls=insignias[f["estado"]][1]),
                                P(f["mensaje"], cls="text-sm") if f["mensaje"] else ""))
                          for f in filas]),
                  cls="uk-table uk-table-divider uk-table-small text-sm"),
            cls="max-h-96 overflow-y-auto border border-border rounded-md mb-4"),
        Form(Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button(f"Registrar {nuevas} capacitación(es)", type="submit", cls=ButtonT.primary, disabled=not nuevas),
                 cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/importar/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-4xl")


@rt(f"{BASE}/importar/confirmar")
def post(auth, sess, contenido: str = ""):
    if not _registra(auth, _marco()):
        return _no()
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return _form_importar(["No se pudo leer el archivo. Súbalo otra vez."])
    filas, _ = importar_capacitacion.leer(datos)
    n = importar_capacitacion.aplicar(filas, auth["id"])
    add_toast(sess, f"Se registraron {n} capacitación(es).", "success")
    return Redirect(BASE)
