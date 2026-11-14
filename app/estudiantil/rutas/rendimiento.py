"""Vacantes de admisión y rendimiento por asignatura (PLAN §72, etapa 7), dentro de Cohortes estudiantiles. Ven quienes ven
el seguimiento estudiantil (agregados); registran y cargan la Dirección de Carrera y Gestión de datos."""
import base64
from datetime import date

from fasthtml.common import (A, APIRouter, Code, Div, Input, Option, P, Redirect, Response, Select, Span, Table, Tbody,
                             Td, Th, Thead, Tr, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, LabelInput, TextPresets, UkIcon

from app.comun import formato
from app.comun.componentes.layout import ID_MODAL, campo, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.estudiantil import rendimiento as rd
from app.estudiantil.rutas.cohortes import BASE, _puede_cargar, _puede_ver

rt = APIRouter()
VACANTES = f"{BASE}/vacantes"
RENDIMIENTO = f"{BASE}/rendimiento"


def _no():
    return Response("No autorizado", status_code=403)


def _volver():
    return A(UkIcon("arrow-left", height=14, width=14), "Cohortes estudiantiles", href=BASE,
             cls="inline-flex items-center gap-1 text-sm text-primary mb-4")


def _num(v, sufijo=""):
    return "—" if v is None else f"{formato.numero(v)}{sufijo}"


# --- Vacantes -----------------------------------------------------------------------------------------------------------------

def _form_vacantes(d=None, errores=()):
    d = d or {}
    return Form(mensaje_error(*errores),
                Div(LabelInput("Año", id="anio", type="number", min=1990, max=2100, value=d.get("anio") or date.today().year,
                               required=True),
                    campo("Semestre", Select(*[Option(c, selected=c == d.get("ciclo", "I")) for c in rd.CICLOS_ADMISION],
                                             name="ciclo", id="ciclo", cls="uk-select")),
                    LabelInput("Vacantes ofertadas", id="vacantes", type="number", min=0, value=d.get("vacantes") or "",
                               required=True),
                    LabelInput("Postulantes (opcional)", id="postulantes", type="number", min=0,
                               value=d.get("postulantes") if d.get("postulantes") is not None else ""),
                    cls="grid grid-cols-2 sm:grid-cols-4 gap-3"),
                LabelInput("Nota (opcional)", id="nota", value=d.get("nota") or "", maxlength=500,
                           placeholder="Criterio con que se fijaron, resolución…"),
                Div(Button("Guardar", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end"),
                P("Si la admisión ya está registrada, se corrige. Los admitidos salen de las cohortes cargadas.",
                  cls=TextPresets.muted_sm),
                hx_post=VACANTES, hx_target="#form-vacantes", hx_select="#form-vacantes", hx_swap="outerHTML",
                id="form-vacantes", cls="space-y-3")


@rt(VACANTES)
def get(auth):
    if not _puede_ver(auth):
        return _no()
    carga = _puede_cargar(auth)
    filas = rd.vacantes()
    return pagina(
        "Vacantes de admisión",
        _volver(),
        H2("Vacantes de admisión"),
        P("Vacantes ofertadas y postulantes de cada admisión; los admitidos son los ingresantes de esa cohorte. La cobertura "
          "es admitidos / vacantes.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(H3("Registrar una admisión", cls="text-base font-semibold mb-2"), _form_vacantes(), cls="mb-6") if carga else "",
        Card(Table(Thead(Tr(Th("Admisión"), Th("Vacantes", cls="text-right"), Th("Postulantes", cls="text-right"),
                            Th("Admitidos", cls="text-right"), Th("Cobertura", cls="text-right"),
                            Th("Postulantes por vacante", cls="text-right"), Th("Nota"), Th("") if carga else "")),
                   Tbody(*[Tr(Td(f"{f['ciclo']}-{f['anio']}", cls="font-medium"),
                              Td(str(f["vacantes"]), cls="text-right tabular-nums"),
                              Td(_num(f["postulantes"]), cls="text-right tabular-nums"),
                              Td(str(f["admitidos"]), cls="text-right tabular-nums"),
                              Td(_num(f["cobertura"], " %"), cls="text-right tabular-nums"),
                              Td(_num(f["postulantes_por_vacante"]), cls="text-right tabular-nums"),
                              Td(f["nota"] or "", cls="text-sm"),
                              Td(Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.xs),
                                        aria_label=f"Quitar la admisión {f['ciclo']}-{f['anio']}",
                                        hx_delete=f"{VACANTES}/{f['id']}", hx_target="body",
                                        hx_confirm="¿Quitar el registro de esta admisión?")) if carga else "")
                           for f in filas]),
                   cls="uk-table uk-table-divider uk-table-small text-sm", data_tabla="vacantes",
                   aria_label="Vacantes por admisión")) if filas else
        P("Aún no hay admisiones registradas.", cls=TextPresets.muted_sm),
        usuario=auth, seccion="docencia")


@rt(VACANTES)
def post(auth, sess, anio: str = "", ciclo: str = "", vacantes: str = "", postulantes: str = "", nota: str = ""):
    if not _puede_cargar(auth):
        return _no()
    d = {"anio": anio, "ciclo": ciclo, "vacantes": vacantes, "postulantes": postulantes, "nota": nota}
    x, errores = rd.guardar_vacantes(d, auth["id"])
    if errores:
        return _form_vacantes(d, errores)
    auditar(auth["id"], "registrar_vacantes", "vacante_admision", None, f"{ciclo}-{anio}: {x['vacantes']} vacantes")
    add_toast(sess, f"Admisión {ciclo}-{anio} guardada.", "success")
    return Redirect(VACANTES)


@rt(f"{VACANTES}/{{vid}}")
def delete(auth, sess, vid: int):
    if not _puede_cargar(auth):
        return _no()
    if rd.eliminar_vacantes(vid):
        auditar(auth["id"], "quitar_vacantes", "vacante_admision", vid, "")
        add_toast(sess, "Registro quitado.", "success")
    return Redirect(VACANTES)


# --- Rendimiento ---------------------------------------------------------------------------------------------------------------

def _celdas(f):
    return [Td(str(f["inscritos"]), cls="text-right tabular-nums"), Td(str(f["aprobados"]), cls="text-right tabular-nums"),
            Td(str(f["reprobados"]), cls="text-right tabular-nums"), Td(str(f["abandonos"]), cls="text-right tabular-nums"),
            Td(_num(f["aprobacion"], " %"), cls="text-right tabular-nums"),
            Td(_num(f["abandono"], " %"), cls="text-right tabular-nums")]


CABECERA = [Th("Inscritos", cls="text-right"), Th("Aprobados", cls="text-right"), Th("Reprobados", cls="text-right"),
            Th("Abandonos", cls="text-right"), Th("Aprobación", cls="text-right"), Th("Abandono", cls="text-right")]


@rt(RENDIMIENTO)
def get(auth, gestion: str = ""):
    if not _puede_ver(auth):
        return _no()
    gs = rd.gestiones()
    g = rd._gestion(gestion) if gestion else (gs[0] if gs else None)
    g = g if g in gs else (gs[0] if gs else None)
    filas = rd.por_asignatura(*g) if g else []
    lineas = rd.por_linea(filas)
    ocultas = sum(f["oculta"] for f in filas)
    selector = Form(Select(*[Option(f"{c}-{a}", value=f"{c}-{a}", selected=(a, c) == g) for a, c in gs], name="gestion",
                           aria_label="Gestión", cls="uk-select uk-form-small w-36"),
                    Button("Ver", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                    A(UkIcon("download", height=14, width=14), "CSV", href=f"{RENDIMIENTO}/csv?gestion={g[1]}-{g[0]}",
                      cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1") if g else "",
                    method="get", action=RENDIMIENTO, cls="flex flex-wrap items-center gap-2 mb-4") if gs else ""
    return pagina(
        "Rendimiento por asignatura",
        _volver(),
        Div(Div(H2("Rendimiento por asignatura"),
                P("Agregados del Sistema de Seguimiento Académico por asignatura y gestión: sin RU, nombres ni notas. Una "
                  f"asignatura con menos de {rd.MIN_CELDA} inscritos se muestra como «menos de {rd.MIN_CELDA}» y no entra "
                  "en los totales, para que no se pueda deducir por resta.", cls=(TextPresets.muted_sm, "max-w-3xl"))),
            Button(UkIcon("upload", height=16, width=16), "Cargar CSV", cls=ButtonT.primary, hx_get=f"{RENDIMIENTO}/importar",
                   hx_target=f"#{ID_MODAL}") if _puede_cargar(auth) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        selector,
        Card(H3("Por línea formativa", cls="text-base font-semibold mb-2"),
             Table(Thead(Tr(Th("Línea formativa"), Th("Asignaturas", cls="text-right"), *CABECERA)),
                   Tbody(*[Tr(Td(x["linea"], cls="font-medium" if x["linea"] == "Total de la gestión" else ""),
                              Td(str(x["asignaturas"]), cls="text-right tabular-nums"), *_celdas(x)) for x in lineas]),
                   cls="uk-table uk-table-divider uk-table-small text-sm", aria_label="Rendimiento por línea formativa"),
             P(f"{ocultas} asignatura(s) con menos de {rd.MIN_CELDA} inscritos no entran en estos totales."
               if ocultas else "", cls=TextPresets.muted_sm), cls="mb-6") if lineas else "",
        Card(H3("Por asignatura", cls="text-base font-semibold mb-2"),
             Table(Thead(Tr(Th("Asignatura"), Th("Línea formativa"), *CABECERA)),
                   Tbody(*[Tr(Td(Span(f["sigla"], cls="font-mono mr-1"), f["nombre"]), Td(f["linea"] or "—"),
                              *(_celdas(f) if not f["oculta"] else
                                [Td(f"menos de {rd.MIN_CELDA}", colspan=6, cls="text-muted-foreground text-sm")]))
                           for f in filas]),
                   cls="uk-table uk-table-divider uk-table-small text-sm", data_tabla="rendimiento",
                   aria_label="Rendimiento por asignatura")) if filas else
        P("Aún no hay datos de rendimiento. Cargue el CSV agregado del Sistema de Seguimiento Académico.",
          cls=TextPresets.muted_sm),
        usuario=auth, seccion="docencia")


@rt(f"{RENDIMIENTO}/csv")
def get(auth, gestion: str = ""):
    if not _puede_ver(auth):
        return _no()
    g = rd._gestion(gestion)
    if not g:
        return Response("Gestión no válida", status_code=404)
    return Response(rd.a_csv(*g).encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="rendimiento-{g[1]}-{g[0]}.csv"'})


def _form_importar(errores=()):
    return modal("Cargar rendimiento por asignatura",
                 Form(mensaje_error(*errores),
                      P("Un CSV con una fila por asignatura y gestión: ", Code("sigla"), ", ", Code("gestion"), " (I-2025, "
                        "II-2025, INV-2025 o VER-2025), ", Code("inscritos"), ", ", Code("aprobados"), ", ",
                        Code("reprobados"), " y ", Code("abandonos"), ". Solo cifras: no incluya RU, nombres ni notas.",
                        cls="text-sm"),
                      P("Una asignatura y gestión ya cargadas se reemplazan. Primero verá una vista previa.",
                        cls=TextPresets.muted_sm),
                      A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{RENDIMIENTO}/plantilla",
                        cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
                      Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
                      Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                          Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
                      hx_post=f"{RENDIMIENTO}/revisar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}",
                      cls="space-y-4"), ancho="max-w-2xl")


@rt(f"{RENDIMIENTO}/importar")
def get(auth):
    return _form_importar() if _puede_cargar(auth) else _no()


@rt(f"{RENDIMIENTO}/plantilla")
def get(auth):
    if not _puede_cargar(auth):
        return _no()
    return Response(rd.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-rendimiento.csv"'})


ESTADOS = {"nueva": ("Nueva", "azul"), "reemplaza": ("Reemplaza", "gris"), "error": ("Error", "rojo")}


@rt(f"{RENDIMIENTO}/revisar")
async def post(auth, archivo: UploadFile = None):
    if not _puede_cargar(auth):
        return _no()
    if archivo is None or not archivo.filename:
        return _form_importar(["Seleccione un archivo."])
    contenido = await archivo.read(rd.MAX_BYTES + 1)
    filas, errores = rd.leer(contenido)
    if not filas:
        return _form_importar(errores)
    validas = sum(f["estado"] != "error" for f in filas)
    return modal(
        "Vista previa del rendimiento",
        P(f"{validas} fila(s) se guardarán · {len(filas) - validas} con errores, se omiten.", cls="text-sm font-medium mb-3"),
        Div(Table(Thead(Tr(Th("Línea"), Th("Sigla"), Th("Gestión"), Th("Resultado"))),
                  Tbody(*[Tr(Td(str(f["linea"])), Td(f["sigla"]), Td(f["gestion"]),
                             Td(insignia(*ESTADOS[f["estado"]]), P(f["mensaje"], cls="text-sm") if f["mensaje"] else ""))
                          for f in filas]), cls="uk-table uk-table-divider uk-table-small text-sm"),
            cls="max-h-96 overflow-y-auto border border-border rounded-md mb-4"),
        Form(Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button(f"Guardar {validas} fila(s)", type="submit", cls=ButtonT.primary, disabled=not validas),
                 cls="flex justify-end gap-2"),
             hx_post=f"{RENDIMIENTO}/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-3xl")


@rt(f"{RENDIMIENTO}/confirmar")
def post(auth, sess, contenido: str = ""):
    if not _puede_cargar(auth):
        return _no()
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return _form_importar(["No se pudo leer el archivo. Súbalo otra vez."])
    filas, errores = rd.leer(datos)
    if not filas:
        return _form_importar(errores)
    n = rd.aplicar(filas, auth["id"])
    auditar(auth["id"], "cargar_rendimiento", "rendimiento_asignatura", None, f"{n} fila(s)")
    add_toast(sess, f"Se guardaron {n} fila(s) de rendimiento.", "success")
    return Redirect(RENDIMIENTO)
