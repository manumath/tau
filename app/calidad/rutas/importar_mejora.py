"""Carga del plan de mejora por CSV (PLAN §72, etapa 4): plantilla, vista previa con responsables e indicadores propuestos,
y confirmación. Solo quien gestiona el plan (`gestionar_plan_mejora`)."""
import base64

from fasthtml.common import A, APIRouter, Code, Div, Input, Li, P, Redirect, Response, Span, Ul, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Form, TextPresets, UkIcon

from app.calidad import importar_mejora as im
from app.calidad import actividades_mejora as am
from app.calidad.rutas.mejora import BASE, _gestiona, _marco, _no_autorizado
from app.comun import formato
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
URL = f"{BASE}/importar"


def _form(errores=()):
    return modal(
        "Cargar el plan de mejora",
        Form(mensaje_error(*errores),
             P("Suba un CSV con una fila por actividad y las columnas de su acción repetidas: ", Code("accion"), " (código, "
               "«A4»), ", Code("accion_titulo"), ", ", Code("actividad"), " («4.2»), ", Code("descripcion"), " y ", Code("fin"),
               " (mes/año o fecha) son obligatorias; las demás (objetivo, responsables, prioridad P1–P3, presupuesto y "
               "fuente, verificación, indicador, línea base, meta, difusión, inicio) se cargan si están.", cls="text-sm"),
             P("Los responsables del archivo son unidades: verá a quién propone el sistema y podrá cambiarlo después en cada "
               "acción. Las acciones cuyo código ya está en el plan se omiten. Primero verá una vista previa.",
               cls=TextPresets.muted_sm),
             A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{URL}/plantilla",
               cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
             Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{URL}/revisar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-2xl")


@rt(URL)
def get(auth):
    return _form() if _gestiona(auth, _marco()) else _no_autorizado()


@rt(f"{URL}/plantilla")
def get(auth):
    if not _gestiona(auth, _marco()):
        return _no_autorizado()
    return Response(im.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-plan-de-mejora.csv"'})


def _nombre(u):
    return f"{u['nombres']} {u['apellidos']}" if u else None


ESTADOS = {"nueva": ("Nueva", "azul"), "existe": ("Ya está en el plan", "gris"), "error": ("Con errores", "rojo")}


def _accion(a):
    titulo, tono = ESTADOS[a["estado"]]
    validas = [t for t in a["actividades"] if not t["errores"]]
    actividades = []
    for t in a["actividades"]:
        clave = f"{a['codigo']}|{t['codigo']}"
        linea = [Span(t["codigo"], cls="font-mono text-muted-foreground mr-1"), t["datos"]["descripcion"].split("\n")[0][:110],
                 Span(f" · {formato.fecha(t['datos']['plazo'])}" if t["datos"]["plazo"] else "", cls=TextPresets.muted_sm)]
        extra = []
        if t["errores"]:
            extra.append(P(f"Línea {t['linea']}: " + " ".join(t["errores"]) + " Se omite.", cls="text-sm text-destructive"))
        elif a["estado"] == "nueva" and t["indicador"]:
            extra.append(Div(Input(type="checkbox", name="ligar", value=clave, checked=True, id=f"ligar-{clave}",
                                   cls="uk-checkbox"),
                             Span(f"Ligar al indicador «{t['indicador']['nombre']}»", cls="text-sm"),
                             cls="flex items-center gap-2 mt-1", title="La línea base del archivo queda como texto."))
        if t["responsable"] and a["estado"] == "nueva":
            extra.append(P(f"A cargo de {_nombre(t['responsable'])} ({t['datos']['unidad_responsable']}).",
                           cls=TextPresets.muted_sm))
        actividades.append(Li(Div(*linea), *extra, cls="py-1"))
    resp = _nombre(a.get("responsable"))
    return Div(
        Div(Div(Span(a["codigo"], cls="font-mono text-muted-foreground mr-2"), Span(a["titulo"], cls="font-medium")),
            Div(insignia(am.PRIORIDAD_P.get(a["prioridad"], "P2"), "gris") if a.get("prioridad") else "",
                insignia(titulo, tono), cls="flex gap-1 shrink-0"), cls="flex items-start justify-between gap-2"),
        P(f"{len(validas)} de {len(a['actividades'])} actividades"
          + (f" · responsable: {resp} (propuesto por «{a['responsable_texto']}»)" if resp and a["estado"] == "nueva" else
             f" · responsable: usted, mientras no se asigne a otra persona ({a['responsable_texto'] or 'sin unidad'})"
             if a["estado"] == "nueva" else ""), cls=TextPresets.muted_sm),
        Ul(*[P(m, cls="text-sm text-destructive") for m in a["mensajes"]]) if a["mensajes"] else "",
        Ul(*actividades, cls="mt-1 ml-1 divide-y divide-border") if a["estado"] == "nueva" else "",
        cls="rounded-md border border-border p-3")


@rt(f"{URL}/revisar")
async def post(auth, archivo: UploadFile = None):
    m = _marco()
    if not _gestiona(auth, m):
        return _no_autorizado()
    if archivo is None or not archivo.filename:
        return _form(["Seleccione un archivo."])
    contenido = await archivo.read(im.MAX_BYTES + 1)
    acciones, errores = im.leer(contenido, m["id"], auth["id"])
    if not acciones:
        return _form(errores)
    nuevas = [a for a in acciones if a["estado"] == "nueva"]
    n_act = sum(1 for a in nuevas for t in a["actividades"] if not t["errores"])
    return modal(
        "Vista previa del plan de mejora",
        P(f"{len(nuevas)} acción(es) nueva(s) con {n_act} actividad(es) · "
          f"{sum(a['estado'] == 'existe' for a in acciones)} ya en el plan · "
          f"{sum(a['estado'] == 'error' for a in acciones)} con errores, se omiten.", cls="text-sm font-medium mb-3"),
        Form(Div(*[_accion(a) for a in acciones], cls="space-y-3 max-h-[28rem] overflow-y-auto mb-4"),
             Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button(f"Cargar {len(nuevas)} acción(es)", type="submit", cls=ButtonT.primary, disabled=not nuevas),
                 cls="flex justify-end gap-2"),
             hx_post=f"{URL}/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-4xl")


@rt(f"{URL}/confirmar")
async def post(auth, sess, req):
    m = _marco()
    if not _gestiona(auth, m):
        return _no_autorizado()
    form = await req.form()
    try:
        datos = base64.b64decode(form.get("contenido", ""), validate=True)
    except ValueError:
        return _form(["No se pudo leer el archivo. Súbalo otra vez."])
    acciones, errores = im.leer(datos, m["id"], auth["id"])
    if not acciones:
        return _form(errores)
    n_acc, n_act = im.aplicar(acciones, m["id"], auth["id"], set(form.getlist("ligar")))
    auditar(auth["id"], "cargar_plan_mejora", "marco_calidad", m["id"], f"{n_acc} acciones, {n_act} actividades")
    add_toast(sess, f"Se cargaron {n_acc} acción(es) con {n_act} actividad(es).", "success")
    return Redirect(BASE)
