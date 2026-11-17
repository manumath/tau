"""Evidencias del marco de calidad (PLAN §57, etapa 4): documentos, enlaces e informes generados por el sistema, asociados a
criterios, con vigencia y huella SHA-256. Las registran la Dirección de Carrera y la Comisión de calidad
(`registrar_evidencias_calidad`); las ven quienes tienen `ver_evidencias_calidad`."""
from urllib.parse import quote, urlencode

from fasthtml.common import (A, APIRouter, Code, Div, FileResponse, Input, Label, Option, P, Redirect, Response,
                             Select, Span, Table, Tbody, Td, Th, Thead, Tr, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, CheckboxX, Form, FormLabel, LabelInput, LabelTextArea, \
    TextPresets, UkIcon

from app.calidad import actividades_mejora as am
from app.calidad import cuerpo_academico, evidencias, indicadores, marco
from app.informes.rutas.anexo import contenido_xlsx as xlsx_informe_idi
from app.comun.componentes.informe import descarga
from app.comun import exportar, permisos, unidades
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina, campo
from app.comun.componentes.registros import fecha_local, insignia
from app.comun.db import auditar
from app.comun import adjuntos

rt = APIRouter()
BASE = "/calidad/evidencias"
# Informes que el sistema guarda solo (no se eligen en «Guardar informe»): el del cierre de un corte (PLAN §72).
OTROS_INFORMES = {"corte_mejora": "Corte del plan de mejora"}
INFORMES = {"indicadores": "Tablero de indicadores de calidad", "marco": "Marco de calidad",
            "informe_idi": "Informe de I+D+i", "cuerpo_academico": "Indicadores del cuerpo académico"}
TONO = {"documento": ("gris", "file-text"), "enlace": ("azul", "link"), "informe": ("verde", "file-spreadsheet")}


def _no_autorizado():
    return Response("No autorizado", status_code=403)


def _no_encontrado():
    return Response("No encontrado", status_code=404)


def _marco():
    return marco.de_unidad(unidades.carrera())


def _fecha(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "—"


def _corta(sha):
    return f"{sha[:12]}…" if sha else ""


# --- Informes del sistema que se pueden guardar como evidencia ------------------------------------------------

def _informes(auth) -> dict[str, str]:
    """Los informes que la cuenta puede generar (no se guarda como evidencia lo que la cuenta no puede ver)."""
    puede = {"informe_idi": permisos.puede(auth, "ver_informes_institucionales", unidades.instituto()),
             "cuerpo_academico": permisos.puede(auth, "ver_informes_institucionales")}
    return {k: t for k, t in INFORMES.items() if puede.get(k, True)}


def generar(clave: str, m: dict, desde: int, hasta: int) -> tuple[bytes, str, str]:
    """(contenido XLSX, nombre del archivo, parámetros) del informe."""
    if clave == "marco":
        return marco.a_xlsx(m["id"]), f"marco-de-calidad-{m['version']}.xlsx", f"versión {m['version']}"
    periodo = f"{desde}–{hasta}"
    if clave == "indicadores":
        t = indicadores.tablero(m["id"], desde, hasta)
        return indicadores.a_xlsx(m["id"], t), f"indicadores-de-calidad-{desde}-{hasta}.xlsx", periodo
    if clave == "informe_idi":
        return xlsx_informe_idi(desde, hasta), f"informe-idi-{desde}-{hasta}.xlsx", f"{periodo}, revistas verificadas"
    filas = cuerpo_academico.filas_indicadores(cuerpo_academico.indicadores(desde, hasta))
    return exportar.a_xlsx(filas), f"cuerpo-academico-{desde}-{hasta}.xlsx", periodo


def _periodo(desde: str, hasta: str, m) -> tuple[int, int, list[str]]:
    anios = indicadores.anios_de(m)
    try:
        d, h = int(desde or anios[0]), int(hasta or anios[-1])
    except ValueError:
        return anios[0], anios[-1], ["Los años del periodo son números."]
    if not (2000 <= d <= h <= anios[-1]) or h - d > 10:
        return d, h, [f"El periodo va de 2000 a {anios[-1]}, de a lo más 11 años, y empieza antes de terminar."]
    return d, h, []


# --- Lista ----------------------------------------------------------------------------------------------------

def _criterios_chips(e):
    return Div(*[A(Span(c["codigo"], cls="font-mono"), href=f"/calidad/marco#criterio-{c['id']}", title=c["nombre"],
                   cls="text-xs rounded bg-muted px-1.5 py-0.5 hover:underline") for c in e["criterios"]],
               cls="flex flex-wrap gap-1")


def _vigencia(e):
    if e["vencida"]:
        return insignia(f"Venció el {_fecha(e['vigente_hasta'])}", "ambar", icono="clock")
    return Span(f"Hasta el {_fecha(e['vigente_hasta'])}" if e["vigente_hasta"] else "Sin vencimiento",
                cls=TextPresets.muted_sm)


def _tipo(e):
    tono, icono = TONO[e["tipo"]]
    return insignia(evidencias.TIPOS[e["tipo"]], tono, icono=icono)


def _filtros(criterios, criterio, estado):
    return Form(
        Select(Option("Todos los criterios", value=""),
               *[Option(f"{c['codigo']} {c['nombre']}", value=str(c["id"]), selected=c["id"] == criterio)
                 for c in criterios], name="criterio", aria_label="Criterio", cls="uk-select uk-form-small max-w-xs"),
        Select(*[Option(t, value=v, selected=v == estado) for v, t in
                 (("", "Vigentes y vencidas"), ("vigentes", "Solo vigentes"), ("vencidas", "Solo vencidas"))],
               name="estado", aria_label="Vigencia", cls="uk-select uk-form-small w-48"),
        Button("Filtrar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        method="get", action=BASE, cls="flex flex-wrap items-center gap-2 mb-4")


@rt(BASE)
def get(auth, criterio: str = "", estado: str = ""):
    m = _marco()
    if not marco.puede(auth, "ver_evidencias_calidad", m):
        return _no_autorizado()
    registra = marco.puede(auth, "registrar_evidencias_calidad", m)
    crit = evidencias.criterios_del_marco(m["id"])
    cid = int(criterio) if criterio.isdigit() and int(criterio) in {c["id"] for c in crit} else None
    estado = estado if estado in ("vigentes", "vencidas") else ""
    lista = evidencias.listar(m["id"], cid, estado)
    sin = [c for c in crit if c["id"] not in evidencias.conteo_por_criterio(m["id"])]
    q = f"?criterio={cid}" if cid else ""
    return pagina(
        "Evidencias",
        Div(Div(H2("Evidencias"),
                P(m["nombre"], " · versión ", m["version"], cls=TextPresets.muted_sm)),
            Div(Button(UkIcon("shield-check", height=14, width=14), "Verificar un archivo",
                       cls=(ButtonT.default, ButtonT.sm), hx_get=f"{BASE}/verificar", hx_target=f"#{ID_MODAL}"),
                *([Button(UkIcon(icono, height=14, width=14), texto, cls=(ButtonT.default, ButtonT.sm),
                          hx_get=f"{BASE}/nueva?{urlencode({'tipo': tipo, **({'criterio': cid} if cid else {})})}",
                          hx_target=f"#{ID_MODAL}")
                   for tipo, texto, icono in (("documento", "Subir documento", "upload"),
                                              ("enlace", "Agregar enlace", "link"),
                                              ("informe", "Guardar informe", "file-spreadsheet"))] if registra else []),
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P("Documentos (actas, resoluciones, convenios…), enlaces e informes generados por el sistema que respaldan los "
          "criterios del marco. Cada archivo guarda su huella: con «Verificar un archivo» se comprueba si un archivo es "
          "idéntico al registrado.", cls="text-sm max-w-3xl mb-4"),
        P(UkIcon("info", height=14, width=14), f" {len(sin)} de {len(crit)} criterios aún no tienen evidencia vigente.",
          cls="text-sm flex items-center gap-1 mb-4") if crit and sin else "",
        _filtros(crit, cid, estado),
        Div(Table(
            Thead(Tr(Th("Evidencia"), Th("Tipo", cls="w-36"), Th("Fecha", cls="w-24"), Th("Criterios", cls="w-44"),
                     Th("Vigencia", cls="w-40"))),
            Tbody(*[Tr(Td(A(e["titulo"], href=f"{BASE}/{e['id']}{q}", cls="font-medium hover:underline"),
                          Div(e["descripcion"], cls=(TextPresets.muted_sm, "line-clamp-2")) if e["descripcion"] else ""),
                       Td(_tipo(e)), Td(_fecha(e["fecha"]), cls="whitespace-nowrap"), Td(_criterios_chips(e)),
                       Td(_vigencia(e))) for e in lista]),
            cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[48rem]"), cls="overflow-x-auto")
        if lista else P("No hay evidencias" + (" con ese filtro." if cid or estado else " registradas."),
                        cls=TextPresets.muted_sm),
        usuario=auth)


# --- Verificar un archivo ---------------------------------------------------------------------------------------

def _form_verificar(resultado=""):
    return modal(
        "Verificar un archivo",
        P("Elija un archivo (por ejemplo, un informe que se entregó) para saber si es idéntico a una evidencia registrada. "
          "El archivo solo se usa para calcular su huella: no se guarda.", cls="text-sm mb-4"),
        Form(Input(type="file", name="archivo", required=True, aria_label="Archivo"),
             Div(Button("Cerrar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Verificar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/verificar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}",
             cls="space-y-4"),
        Div(resultado, cls="mt-4"))


@rt(f"{BASE}/verificar")
def get(auth):
    m = _marco()
    return _form_verificar() if marco.puede(auth, "ver_evidencias_calidad", m) else _no_autorizado()


@rt(f"{BASE}/verificar")
async def post(auth, archivo: UploadFile = None):
    m = _marco()
    if not marco.puede(auth, "ver_evidencias_calidad", m):
        return _no_autorizado()
    if archivo is None or not archivo.filename:
        return _form_verificar(mensaje_error("Seleccione un archivo."))
    contenido = await archivo.read(evidencias.MAX_BYTES + 1)
    if len(contenido) > evidencias.MAX_BYTES:
        return _form_verificar(mensaje_error("El archivo supera los 20 MB: no puede ser una evidencia registrada."))
    sha = evidencias.huella(contenido)
    iguales = evidencias.por_huella(sha)
    if not iguales:
        resultado = Card(H3("No coincide", cls="text-base font-semibold"),
                         P("Ninguna evidencia registrada tiene este archivo: no es idéntico a ninguno (basta un cambio "
                           "mínimo para que la huella cambie).", cls="text-sm"),
                         P("SHA-256: ", Code(sha, cls="text-xs break-all"), cls="text-sm"))
    else:
        resultado = Card(H3(UkIcon("shield-check", height=16, width=16), " Coincide", cls="text-base font-semibold"),
                         P("El archivo es idéntico al de:", cls="text-sm"),
                         *[P(A(e["titulo"], href=f"{BASE}/{e['id']}", cls="text-primary hover:underline"),
                             f", registrada el {fecha_local(e['registrado_en'])}", cls="text-sm") for e in iguales],
                         P("SHA-256: ", Code(sha, cls="text-xs break-all"), cls="text-sm"))
    return _form_verificar(resultado)


# --- Alta y edición ---------------------------------------------------------------------------------------------

def form_evidencia(m, tipo, d, url, metodo, auth, errores=()):
    def v(k):
        return d.get(k) or ""
    marcados = {int(c) for c in d.get("criterios") or []}
    nuevo = metodo == "post"
    especifico = ""
    if tipo == "documento" and nuevo:
        especifico = Div(FormLabel("Archivo", fr="archivo"),
                         Input(type="file", id="archivo", name="archivo", required=True,
                               accept=".pdf,.png,.jpg,.jpeg,.xlsx,.docx,.pptx"),
                         P(f"{evidencias.FORMATOS}, hasta 20 MB. El archivo no se puede reemplazar después: para una "
                           "versión nueva, registre otra evidencia.", cls=TextPresets.muted_sm), cls="space-y-2")
    elif tipo == "enlace":
        especifico = LabelInput("Dirección (https://…)", id="url", value=v("url"), required=True, type="url")
    elif tipo == "informe" and nuevo:
        anios = indicadores.anios_de(m)
        especifico = Div(
            Div(FormLabel("Informe", fr="informe"),
                Select(*[Option(t, value=k, selected=k == v("informe")) for k, t in _informes(auth).items()],
                       id="informe", name="informe", cls="uk-select"), cls="space-y-2 sm:col-span-2"),
            LabelInput("Desde el año", id="desde", type="number", value=v("desde") or anios[0], min=2000),
            LabelInput("Hasta el año", id="hasta", type="number", value=v("hasta") or anios[-1], min=2000),
            P("El sistema genera el informe (XLSX) con los datos de hoy y lo guarda con su huella; el marco de calidad "
              "no usa el periodo.", cls=(TextPresets.muted_sm, "sm:col-span-4")),
            cls="grid grid-cols-2 sm:grid-cols-4 gap-4")
    por_dim: dict[str, list] = {}
    for c in evidencias.criterios_del_marco(m["id"]):
        por_dim.setdefault(f"{c['dimension_codigo']} {c['dimension_nombre']}", []).append(c)
    return modal(
        {"documento": "Subir documento", "enlace": "Agregar enlace", "informe": "Guardar informe del sistema"}[tipo] if nuevo
        else "Editar evidencia",
        Form(mensaje_error(*errores),
             LabelInput("Título", id="titulo", value=v("titulo"), required=True, maxlength=200),
             LabelTextArea("Descripción (opcional)", id="descripcion", value=v("descripcion"), rows=2),
             especifico,
             Div(LabelInput("Fecha del documento", id="fecha", type="date", value=v("fecha")),
                 LabelInput("Vigente hasta (vacío: no vence)", id="vigente_hasta", type="date",
                            value=v("vigente_hasta")), cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             campo("Criterios que respalda", Div(*[Div(Div(dim, cls="text-xs font-medium mt-2"),
                           *[Label(CheckboxX(name="criterios", value=str(c["id"]), checked=c["id"] in marcados),
                                   Span(Span(c["codigo"], cls="font-mono mr-1"), c["nombre"]),
                                   cls="flex items-center gap-2 text-sm") for c in cs])
                       for dim, cs in por_dim.items()],
                     cls="max-h-64 overflow-y-auto rounded border border-border p-3 space-y-1"),
                 cls="space-y-2"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", hx_encoding="multipart/form-data", cls="space-y-4"),
        ancho="max-w-3xl")


def _registrable(auth):
    m = _marco()
    return m, (None if marco.puede(auth, "registrar_evidencias_calidad", m) else _no_autorizado())


@rt(f"{BASE}/nueva")
def get(auth, tipo: str = "documento", criterio: str = ""):
    m, error = _registrable(auth)
    if error:
        return error
    tipo = tipo if tipo in evidencias.TIPOS else "documento"
    return form_evidencia(m, tipo, {"criterios": [criterio] if criterio.isdigit() else []}, f"{BASE}?tipo={tipo}",
                          "post", auth)


@rt(BASE)
async def post(auth, sess, req, tipo: str = "documento"):
    m, error = _registrable(auth)
    if error:
        return error
    tipo = tipo if tipo in evidencias.TIPOS else "documento"
    f = await req.form()
    d = {k: f.get(k, "") for k in ("titulo", "descripcion", "fecha", "vigente_hasta", "url", "informe", "desde", "hasta")}
    d["criterios"] = f.getlist("criterios")
    x, errores = evidencias.validar(d, m["id"], tipo)
    nombre, contenido, informe, parametros = "", b"", None, None
    if tipo == "documento":
        archivo = f.get("archivo")
        if isinstance(archivo, UploadFile) and archivo.filename:
            nombre, contenido = archivo.filename, await archivo.read(evidencias.MAX_BYTES + 1)
        errores += evidencias.validar_archivo(nombre, contenido)
    elif tipo == "informe":
        informe = d["informe"]
        desde, hasta, err = _periodo(d["desde"], d["hasta"], m)
        if informe not in _informes(auth):
            errores.append("Elija un informe de la lista.")
        errores += err
        if not errores:
            contenido, nombre, parametros = generar(informe, m, desde, hasta)
    if errores:
        return form_evidencia(m, tipo, d, f"{BASE}?tipo={tipo}", "post", auth, errores)
    eid = evidencias.crear(m["id"], tipo, x, auth["id"], nombre, contenido, informe, parametros)
    auditar(auth["id"], "crear_evidencia_calidad", "evidencia_calidad", eid, x["titulo"])
    add_toast(sess, "Evidencia registrada.", "success")
    return Redirect(f"{BASE}/{eid}")


# --- Ficha y descarga -------------------------------------------------------------------------------------------

def _visible(auth, eid, accion="ver_evidencias_calidad"):
    e = evidencias.obtener(eid)
    if e is None:
        return None, _no_encontrado()
    if marco.puede(auth, accion, marco.obtener(e["marco_id"])) or (accion == "ver_evidencias_calidad" and _de_su_actividad(auth, e)):
        return e, None
    return e, _no_autorizado()


def _de_su_actividad(auth, e) -> bool:
    """El responsable de una actividad del plan de mejora ve (no edita) las evidencias ligadas a ella (PLAN §72, etapa 11)."""
    t = am.obtener(e["actividad_id"]) if e["actividad_id"] else None
    return bool(t) and am.puede_avanzar(auth, t)


def _dato(titulo, *valor):
    return Div(Div(titulo, cls=TextPresets.muted_sm), Div(*valor, cls="text-sm break-words"), cls="space-y-1")


@rt(f"{BASE}/{{eid}}")
def get(auth, eid: int, criterio: str = ""):
    e, error = _visible(auth, eid)
    if error:
        return error
    m = marco.obtener(e["marco_id"])
    registra = marco.puede(auth, "registrar_evidencias_calidad", m)
    t = am.obtener(e["actividad_id"]) if e["actividad_id"] else None
    url_t = f"/calidad/mejora/actividades/{t['id']}" if t else None
    if marco.puede(auth, "ver_evidencias_calidad", m):
        volver = A(UkIcon("arrow-left", height=14, width=14), "Evidencias",
                   href=f"{BASE}?criterio={criterio}" if criterio.isdigit() else BASE,
                   cls="inline-flex items-center gap-1 text-sm text-primary mb-4")
    else:   # el responsable de la actividad: no tiene el repositorio
        volver = A(UkIcon("arrow-left", height=14, width=14), "La actividad", href=url_t,
                   cls="inline-flex items-center gap-1 text-sm text-primary mb-4")
    return pagina(
        e["titulo"],
        volver,
        Div(Div(H2(e["titulo"]), Div(_tipo(e), _vigencia(e), cls="flex flex-wrap items-center gap-2 mt-2")),
            Div(Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"{BASE}/{eid}/editar", hx_target=f"#{ID_MODAL}"),
                Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
                       hx_delete=f"{BASE}/{eid}", hx_target="body",
                       hx_confirm="¿Eliminar la evidencia? Si tiene archivo, también se borra."),
                cls="flex shrink-0 gap-2") if registra else "",
            cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(Div(_dato("Descripción", e["descripcion"] or "—"),
                 _dato("Actividad del plan de mejora", A(f"{t['accion_codigo'] or ''} {t['codigo'] or ''} "
                                                         f"{am.titulo(t['descripcion'])}".strip(), href=url_t,
                                                         cls="text-primary hover:underline")) if t else "",
                 Div(_dato("Fecha del documento", _fecha(e["fecha"])),
                     _dato("Vigente hasta", _fecha(e["vigente_hasta"]) if e["vigente_hasta"] else "Sin vencimiento"),
                     _dato("Registrada", fecha_local(e["registrado_en"]), f" por {e['por']}" if e["por"] else ""),
                     cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 _dato("Enlace", A(e["url"], href=e["url"], target="_blank", rel="noopener noreferrer",
                                   cls="text-primary hover:underline")) if e["url"] else "",
                 _dato("Informe", f"{INFORMES.get(e['informe']) or OTROS_INFORMES.get(e['informe'], e['informe'])} ({e['parametros']})")
                 if e["informe"] else "",
                 Div(_dato("Archivo", descarga(f"{e['nombre_archivo']} ({adjuntos.tamano_texto(e['tamano'])})",
                                               f"{BASE}/{eid}/archivo")),
                     _dato("Huella SHA-256", Code(e["sha256"], cls="text-xs break-all")),
                     cls="grid grid-cols-1 sm:grid-cols-2 gap-4") if e["archivo"] else "",
                 _dato("Criterios que respalda",
                       Div(*[Div(A(Span(c["codigo"], cls="font-mono mr-2"), c["nombre"],
                                   href=f"/calidad/marco#criterio-{c['id']}", cls="hover:underline"))
                             for c in e["criterios"]], cls="space-y-1") if e["criterios"] else
                       P("Ninguno todavía: la subió el responsable de la actividad; la Comisión de calidad o la Dirección los "
                         "marca al editarla.", cls=TextPresets.muted_sm)),
                 cls="space-y-4")),
        usuario=auth)


@rt(f"{BASE}/{{eid}}/archivo")
def get(auth, eid: int):
    e, error = _visible(auth, eid)
    if error or not e["archivo"]:
        return error or _no_encontrado()
    en_linea = e["mime"] in ("application/pdf", "image/png", "image/jpeg")
    return FileResponse(evidencias.ruta(e), media_type=e["mime"], headers={
        "Content-Disposition": f"{'inline' if en_linea else 'attachment'}; filename*=UTF-8''{quote(e['nombre_archivo'])}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@rt(f"{BASE}/{{eid}}/editar")
def get(auth, eid: int):
    e, error = _visible(auth, eid, "registrar_evidencias_calidad")
    if error:
        return error
    return form_evidencia(marco.obtener(e["marco_id"]), e["tipo"], {**e, "criterios": [c["id"] for c in e["criterios"]]},
                          f"{BASE}/{eid}", "put", auth)


@rt(f"{BASE}/{{eid}}")
async def put(auth, sess, req, eid: int):
    e, error = _visible(auth, eid, "registrar_evidencias_calidad")
    if error:
        return error
    f = await req.form()
    d = {k: f.get(k, "") for k in ("titulo", "descripcion", "fecha", "vigente_hasta", "url")}
    d["criterios"] = f.getlist("criterios")
    x, errores = evidencias.validar(d, e["marco_id"], e["tipo"])
    if errores:
        return form_evidencia(marco.obtener(e["marco_id"]), e["tipo"], d, f"{BASE}/{eid}", "put", auth, errores)
    evidencias.actualizar(e, x)
    auditar(auth["id"], "editar_evidencia_calidad", "evidencia_calidad", eid, x["titulo"])
    add_toast(sess, "Evidencia guardada.", "success")
    return Redirect(f"{BASE}/{eid}")


@rt(f"{BASE}/{{eid}}")
def delete(auth, sess, eid: int):
    e, error = _visible(auth, eid, "registrar_evidencias_calidad")
    if error:
        return error
    evidencias.eliminar(e)
    auditar(auth["id"], "eliminar_evidencia_calidad", "evidencia_calidad", eid,
            f"{e['titulo']}" + (f" (SHA-256 {e['sha256']})" if e["sha256"] else ""))
    add_toast(sess, "Evidencia eliminada.", "success")
    return Redirect(BASE)
