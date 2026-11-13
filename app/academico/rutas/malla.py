"""Editor de la malla de un plan en elaboración: asignaturas por semestre, electivas, ciclos, importación de un CSV y la
lista de verificación para ponerlo en vigencia (PLAN §65, etapa 3). Solo quienes elaboran planes."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Datalist, Div, Input, Option, P, Redirect, Response, Select, Span, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import malla, planes
from app.comun import permisos
from app.comun.componentes.layout import CERRAR, ID_MODAL, campo, cerrar_modal, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import get_db

rt = APIRouter()
BASE = "/docencia/planes"
MAX_CSV = 512 * 1024


def _plan_editable(auth, pid):
    """(plan, None) o (None, respuesta de error): solo quienes elaboran, y solo un plan en elaboración."""
    if not permisos.puede(auth, "elaborar_planes"):
        return None, Response("No autorizado", status_code=403)
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return None, Response("No encontrado", status_code=404)
    return p, None


# --- Lista de verificación ------------------------------------------------------------------------------------------

def panel_verificacion(pid: int):
    puntos = malla.verificar(pid)
    faltan = sum(v["nivel"] == "falta" for v in puntos)
    avisos = sum(v["nivel"] == "aviso" for v in puntos)
    icono = {"ok": ("check", "text-green-800 dark:text-green-300"), "falta": ("circle-x", "text-destructive"),
             "aviso": ("circle-alert", "text-amber-800 dark:text-amber-300")}
    items = [fh.Li(UkIcon(icono[v["nivel"]][0], height=16, width=16, cls=f"shrink-0 mt-0.5 {icono[v['nivel']][1]}"),
                   Div(Span(v["texto"], cls="text-sm"),
                       Div(v["detalle"], cls=TextPresets.muted_sm) if v["detalle"] else ""),
                   cls="flex gap-2 items-start") for v in puntos]
    resumen = insignia("Lista para ponerse en vigencia", "verde", icono="check") if not faltan else \
        insignia(f"Falta{'n' if faltan > 1 else ''} {faltan} punto{'s' if faltan > 1 else ''}", "rojo", icono="circle-x")
    return Card(Div(H3("Para poner en vigencia", cls="text-base font-semibold"), resumen,
                    insignia(f"{avisos} aviso{'s' if avisos != 1 else ''}", "ambar") if avisos else "",
                    cls="flex flex-wrap items-center gap-2 mb-2"),
                fh.Ul(*items, cls="space-y-1"), id="verificacion-plan")


# --- Malla ------------------------------------------------------------------------------------------------------------

def _medidas(f, sistema):
    if sistema == "creditos":
        return [fh.Td(str(f["creditos"]) if f["creditos"] else "—", cls="tabular-nums w-14")]
    return [fh.Td(str(f[c]) if f[c] else "—", cls="tabular-nums w-14")
            for c in ("horas_teoricas", "horas_practicas", "horas_laboratorio")]


def _fila(pid, f, sistema):
    casilla = f["asignatura_id"] is None
    return fh.Tr(
        fh.Td("" if casilla else f["sigla"], cls="font-mono text-sm whitespace-nowrap"),
        fh.Td(Span(planes.TIPOS[f["tipo"]], cls="italic") if casilla else f["nombre"],
              "" if f["tipo"] == "obligatoria" or casilla else Span(f" · {planes.TIPOS[f['tipo']]}",
                                                                    cls=TextPresets.muted_sm), cls="text-sm"),
        *_medidas(f, sistema),
        fh.Td(", ".join(f["requisitos"]) or "—", cls="text-sm whitespace-nowrap"),
        fh.Td(Button(UkIcon("pencil", height=14, width=14), hx_get=f"{BASE}/{pid}/malla/fila/{f['id']}",
                     hx_target=f"#{ID_MODAL}", hx_swap="innerHTML", cls=(ButtonT.ghost, ButtonT.xs),
                     aria_label=f"Editar {f['sigla'] or planes.TIPOS[f['tipo']]}"),
              Button(UkIcon("trash-2", height=14, width=14), hx_post=f"{BASE}/{pid}/malla/fila/{f['id']}/quitar",
                     hx_confirm=f"¿Quitar {f['sigla'] or planes.TIPOS[f['tipo']]} de este plan?",
                     hx_target="#malla", hx_swap="outerHTML", cls=(ButtonT.ghost, ButtonT.xs, "text-destructive"),
                     aria_label=f"Quitar {f['sigla'] or planes.TIPOS[f['tipo']]}"), cls="whitespace-nowrap text-right"),
        id=f"fila-{f['id']}")


def _tabla(pid, filas, sistema):
    if not filas:
        return P("Sin asignaturas todavía.", cls=TextPresets.muted_sm)
    horas = [fh.Th("Créd.", cls="w-14")] if sistema == "creditos" else \
        [fh.Th("T", title="Horas teóricas semanales", cls="w-14"), fh.Th("P", title="Horas prácticas semanales", cls="w-14"),
         fh.Th("L", title="Horas de laboratorio semanales", cls="w-14")]
    return Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), *horas, fh.Th("Requisitos"),
                                       fh.Th(Span("Acciones", cls="sr-only")))),
                        fh.Tbody(*[_fila(pid, f, sistema) for f in filas]),
                        cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")


def _agregar(pid, texto, **params):
    consulta = "&".join(f"{k}={v}" for k, v in params.items())
    return Button(UkIcon("plus", height=14, width=14), texto, hx_get=f"{BASE}/{pid}/malla/fila/nueva?{consulta}",
                  hx_target=f"#{ID_MODAL}", hx_swap="innerHTML", cls=(ButtonT.default, ButtonT.sm))


def malla_fragmento(pid: int, oob=False):
    p = planes.obtener(pid)
    sistema = p["sistema"]
    por_semestre = {s: (c, filas) for s, c, filas in planes.por_semestre(pid)}
    n = max([p["duracion_semestres"] or 0, *por_semestre])
    tarjetas = []
    for s in range(1, n + 1):
        ciclo, filas = por_semestre.get(s, (None, []))
        tarjetas.append(Card(
            Div(H3(f"{planes.ORDINALES[s] if s < len(planes.ORDINALES) else f'{s}.º'} semestre",
                   cls="text-base font-semibold"),
                insignia(f"Ciclo {ciclo}", "azul") if ciclo else "", Div(_agregar(pid, "Agregar", semestre=s),
                                                                         cls="ml-auto"),
                cls="flex flex-wrap items-center gap-2 mb-2"),
            _tabla(pid, filas, sistema), id=f"semestre-{s}"))
    electivas = []
    for g, titulo in planes.GRUPOS_ELECTIVAS.items():
        filas = planes.electivas(pid).get(g, [])
        if filas:
            electivas.append(Card(H3(f"{titulo} ({len(filas)})", cls="text-base font-semibold mb-2"),
                                  _tabla(pid, filas, sistema)))
    return Div(panel_verificacion(pid), *tarjetas or [P("El plan no tiene semestres: agregue uno.")],
               Div(Button(UkIcon("plus", height=14, width=14), "Agregar un semestre", hx_post=f"{BASE}/{pid}/malla/semestre",
                          hx_target="#malla", hx_swap="outerHTML", cls=(ButtonT.default, ButtonT.sm)),
                   _agregar(pid, "Agregar una electiva a la lista", tipo="electiva_a"), cls="flex flex-wrap gap-2"),
               *electivas, id="malla", cls="space-y-4", hx_swap_oob="true" if oob else None)


@rt(f"{BASE}/{{pid}}/malla")
def get(auth, pid: int):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    return pagina(
        f"Malla · {p['programa']} · {p['nombre']}",
        A(UkIcon("arrow-left", height=14, width=14), "Volver al plan", href=f"{BASE}/{pid}",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"Malla de {p['programa']}"),
        P(f"{p['nombre']} · en elaboración · {'créditos' if p['sistema'] == 'creditos' else 'horas semanales'}. "
          "Cada cambio se guarda al instante.", cls=(TextPresets.muted_sm, "mb-4")),
        Div(Button(UkIcon("layers", height=14, width=14), "Ciclos", hx_get=f"{BASE}/{pid}/malla/ciclos",
                   hx_target=f"#{ID_MODAL}", hx_swap="innerHTML", cls=(ButtonT.default, ButtonT.sm)),
            Button(UkIcon("upload", height=14, width=14), "Importar CSV", hx_get=f"{BASE}/{pid}/malla/importar",
                   hx_target=f"#{ID_MODAL}", hx_swap="innerHTML", cls=(ButtonT.default, ButtonT.sm)),
            cls="flex flex-wrap gap-2 mb-4"),
        malla_fragmento(pid), usuario=auth, seccion="docencia")


@rt(f"{BASE}/{{pid}}/malla/semestre")
def post(auth, pid: int):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    actual = max([p["duracion_semestres"] or 0, *[s for s, _, _ in planes.por_semestre(pid)]])
    if actual < malla.MAX_SEMESTRES:
        get_db().execute("UPDATE plan_estudios SET duracion_semestres = ? WHERE id = ?", [actual + 1, pid])
    return malla_fragmento(pid)


# --- Una fila ---------------------------------------------------------------------------------------------------------

def _form_fila(p, f, errores=(), requisitos=None, egresado=False):
    pid = p["id"]
    fid = f.get("id")
    cat = get_db().q("SELECT sigla, nombre FROM asignatura ORDER BY sigla")
    lineas = [r["linea_formativa"] for r in get_db().q(
        "SELECT DISTINCT linea_formativa FROM asignatura WHERE linea_formativa IS NOT NULL ORDER BY 1")]
    elegidos = set(requisitos if requisitos is not None else f.get("requisitos", []))
    en_plan = malla.siglas_del_plan(pid, fid)

    def n(c):
        return "" if f.get(c) is None else str(f[c])
    medidas = Div(campo("Créditos", Input(name="creditos", value=n("creditos"), inputmode="numeric", cls="uk-input")),
                  cls="grid grid-cols-3 gap-3") if p["sistema"] == "creditos" else \
        Div(campo("Horas teóricas", Input(name="horas_teoricas", value=n("horas_teoricas"), inputmode="numeric",
                                          cls="uk-input")),
            campo("Horas prácticas", Input(name="horas_practicas", value=n("horas_practicas"), inputmode="numeric",
                                           cls="uk-input")),
            campo("Horas de laboratorio", Input(name="horas_laboratorio", value=n("horas_laboratorio"),
                                                inputmode="numeric", cls="uk-input")), cls="grid grid-cols-3 gap-3")
    lista_req = Div(*[fh.Label(Input(type="checkbox", name="requisitos", value=r["sigla"], checked=r["sigla"] in elegidos),
                               Span(f"{r['sigla']} · {r['nombre']}", cls="text-sm"), cls="flex items-center gap-2")
                      for r in en_plan] or [P("El plan aún no tiene otras asignaturas.", cls=TextPresets.muted_sm)],
                    cls="max-h-44 overflow-y-auto border border-border rounded-md p-2 space-y-1")
    tipo = f.get("tipo") or "obligatoria"
    return fh.Form(
        mensaje_error(*errores),
        Input(type="hidden", name="fid", value=str(fid or "")),
        Div(campo("Tipo", Select(*[Option(t, value=k, selected=k == tipo) for k, t in malla.TIPOS_FILA.items()],
                                 name="tipo", cls="uk-select")),
            campo("Semestre (vacío en una lista de electivas)",
                  Input(name="semestre", value=n("semestre"), inputmode="numeric", cls="uk-input")),
            campo("Sigla (vacía en una casilla)", Input(name="sigla", value=f.get("sigla") or "", list="catalogo-siglas",
                                                        autocomplete="off", placeholder="MAT-111", cls="uk-input")),
            campo("Nombre (solo si la sigla es nueva)", Input(name="nombre", value=f.get("nombre") or "", cls="uk-input")),
            campo("Línea formativa (solo si la sigla es nueva)",
                  Input(name="linea_formativa", value=f.get("linea_formativa") or "", list="lineas-formativas",
                        cls="uk-input")),
            cls="grid grid-cols-1 md:grid-cols-2 gap-3"),
        Datalist(*[Option(value=r["sigla"], label=r["nombre"]) for r in cat], id="catalogo-siglas"),
        Datalist(*[Option(value=x) for x in lineas], id="lineas-formativas"),
        Div(H3("Horas" if p["sistema"] == "horas" else "Créditos", cls="text-sm font-semibold mt-4 mb-1"), medidas),
        Div(H3("Requisitos", cls="text-sm font-semibold mt-4 mb-1"), lista_req,
            fh.Label(Input(type="checkbox", name="egresado", value="1", checked=bool(egresado or f.get("egresado"))),
                     Span("Exige ser egresado", cls="text-sm"), cls="flex items-center gap-2 mt-2")),
        Div(Button("Guardar", type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=f"{BASE}/{pid}/malla/fila", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
        hx_disabled_elt="find button[type='submit']")


@rt(f"{BASE}/{{pid}}/malla/fila/nueva")
def get(auth, pid: int, semestre: str = "", tipo: str = "obligatoria"):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    return modal("Agregar al plan", _form_fila(p, {"semestre": int(semestre) if semestre.isdigit() else None,
                                                  "tipo": tipo if tipo in malla.TIPOS_FILA else "obligatoria"}),
                 ancho="max-w-2xl")


@rt(f"{BASE}/{{pid}}/malla/fila/{{fid}}")
def get(auth, pid: int, fid: int):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    f = malla.fila(fid)
    if not f or f["plan_id"] != pid:
        return Response("No encontrado", status_code=404)
    return modal("Editar en el plan", _form_fila(p, f), ancho="max-w-2xl")


@rt(f"{BASE}/{{pid}}/malla/fila")
async def post(auth, pid: int, req):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    form = await req.form()
    datos = {k: form.get(k, "") for k in ("tipo", "semestre", "sigla", "nombre", "linea_formativa", "creditos",
                                          "horas_teoricas", "horas_practicas", "horas_laboratorio", "egresado")}
    reqs = form.getlist("requisitos")
    fid = int(form["fid"]) if str(form.get("fid", "")).isdigit() else None
    errores = malla.guardar_fila(pid, fid, datos, reqs, auth["id"])
    if errores:
        return modal("Editar en el plan" if fid else "Agregar al plan",
                     _form_fila(p, {**datos, "id": fid, "sigla": datos["sigla"].upper(),
                                    "semestre": datos["semestre"] or None,
                                    **{c: datos[c] or None for c in ("creditos", "horas_teoricas", "horas_practicas",
                                                                     "horas_laboratorio")}},
                                errores, reqs, bool(datos["egresado"])), ancho="max-w-2xl")
    return cerrar_modal(), malla_fragmento(pid, oob=True)


@rt(f"{BASE}/{{pid}}/malla/fila/{{fid}}/quitar")
def post(auth, sess, pid: int, fid: int):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    huerfanas = malla.quitar_fila(pid, fid, auth["id"])
    if huerfanas is None:
        return Response("No encontrado", status_code=404)
    if huerfanas:
        add_toast(sess, f"Asignatura quitada. {huerfanas} más la tenían como requisito: revise la lista de verificación.",
                  "warning")
    return malla_fragmento(pid)


# --- Ciclos ---------------------------------------------------------------------------------------------------------

def _form_ciclos(pid, errores=(), filas=None):
    filas = filas if filas is not None else [{"nombre": c["nombre"], "desde": c["semestre_desde"],
                                              "hasta": c["semestre_hasta"]} for c in malla.ciclos(pid)]
    filas = (filas + [{}] * 4)[:max(4, len(filas))]
    return fh.Form(
        mensaje_error(*errores),
        P("Un ciclo agrupa semestres consecutivos (por ejemplo, básico: del 1 al 4). El ciclo de cada asignatura se "
          "deduce de su semestre. Deje en blanco las filas que no use.", cls=(TextPresets.muted_sm, "mb-2")),
        *[Div(campo("Nombre", Input(name="ciclo_nombre", value=f.get("nombre", ""), cls="uk-input")),
              campo("Desde el semestre", Input(name="ciclo_desde", value=str(f.get("desde", "") or ""),
                                               inputmode="numeric", cls="uk-input")),
              campo("Hasta el semestre", Input(name="ciclo_hasta", value=str(f.get("hasta", "") or ""),
                                               inputmode="numeric", cls="uk-input")),
              cls="grid grid-cols-3 gap-3 mb-2") for f in filas],
        Div(Button("Guardar", type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=f"{BASE}/{pid}/malla/ciclos", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
        hx_disabled_elt="find button[type='submit']")


@rt(f"{BASE}/{{pid}}/malla/ciclos")
def get(auth, pid: int):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    return modal("Ciclos del plan", _form_ciclos(pid), ancho="max-w-xl")


@rt(f"{BASE}/{{pid}}/malla/ciclos")
async def post(auth, pid: int, req):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    form = await req.form()
    filas = [{"nombre": n, "desde": d, "hasta": h} for n, d, h in zip(
        form.getlist("ciclo_nombre"), form.getlist("ciclo_desde"), form.getlist("ciclo_hasta"))]
    errores = malla.guardar_ciclos(pid, filas, auth["id"])
    if errores:
        return modal("Ciclos del plan", _form_ciclos(pid, errores, filas), ancho="max-w-xl")
    return cerrar_modal(), malla_fragmento(pid, oob=True)


# --- Importar un CSV --------------------------------------------------------------------------------------------------

def _form_importar(pid, errores=()):
    return Div(
        mensaje_error(*errores),
        P("El archivo trae una fila por asignatura o casilla de electiva (las mismas columnas de datos/planes). "
          "REEMPLAZA toda la malla actual del plan. Las siglas nuevas se agregan al catálogo.",
          cls=TextPresets.muted_sm),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{BASE}/{pid}/malla/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        fh.Form(Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
                Div(Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR),
                    Button("Reemplazar la malla", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
                hx_post=f"{BASE}/{pid}/malla/importar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}",
                hx_confirm="Se reemplazará toda la malla actual de este plan. ¿Continuar?", cls="space-y-4"),
        cls="space-y-4")


@rt(f"{BASE}/{{pid}}/malla/importar")
def get(auth, pid: int):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    return modal("Importar la malla de un CSV", _form_importar(pid), ancho="max-w-xl")


@rt(f"{BASE}/{{pid}}/malla/plantilla")
def get(auth, pid: int):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    return Response(malla.plantilla_csv().encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-plan.csv"'})


@rt(f"{BASE}/{{pid}}/malla/importar")
async def post(auth, sess, pid: int, archivo: UploadFile = None):
    p, error = _plan_editable(auth, pid)
    if error:
        return error
    if archivo is None or not archivo.filename:
        return modal("Importar la malla de un CSV", _form_importar(pid, ["Seleccione un archivo."]), ancho="max-w-xl")
    crudo = await archivo.read(MAX_CSV + 1)
    if len(crudo) > MAX_CSV:
        return modal("Importar la malla de un CSV", _form_importar(pid, ["El archivo es demasiado grande."]),
                     ancho="max-w-xl")
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return modal("Importar la malla de un CSV", _form_importar(pid, ["El archivo debe estar en UTF-8."]),
                     ancho="max-w-xl")
    n, errores = malla.importar_csv(pid, texto, auth["id"])
    if errores:
        return modal("Importar la malla de un CSV", _form_importar(pid, errores), ancho="max-w-xl")
    add_toast(sess, f"Malla cargada: {n} filas.", "success")
    return Redirect(f"{BASE}/{pid}/malla")
