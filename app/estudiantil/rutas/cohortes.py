"""Cohortes estudiantiles: tablero de ingreso, egreso, titulación y deserción de la licenciatura, y carga del
CSV de Seguimiento Académico (PLAN §49). Ven el tablero (agregados) la Dirección de Carrera, la
Coordinación académica, Gestión de datos y el Comité de acreditación; cargan el CSV la Dirección de Carrera y
Gestión de datos. Sin materias ni notas."""
import base64

from fasthtml.common import A, APIRouter, Code, Div, P, Redirect, Response, Thead, Tr, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, Form, Input, Label, LabelT, Table, Tbody, Td, TextPresets, Th,
                           UkIcon)

from app.academico.componentes import pestanas
from app.comun import permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.estudiantil import cohortes, importar

rt = APIRouter()
BASE = "/docencia/cohortes"
N_COHORTES = 20


def _puede_ver(auth) -> bool:
    return permisos.puede(auth, "ver_seguimiento_estudiantil", vinculos.carrera())


def _puede_cargar(auth) -> bool:
    return permisos.puede(auth, "gestionar_cohortes", vinculos.carrera())


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f} %"


def _tablero(auth):
    ciclos = cohortes.cohortes_hasta(cohortes.ciclo_actual(), N_COHORTES)
    todos = cohortes.alumnos()
    ind = cohortes.indicadores(todos)
    filas = []
    for c in reversed(cohortes.resumen(ciclos, todos)):
        if not c["n"]:
            continue
        e = c["estados"]
        egresaron = e["egresado"] + e["titulado"]
        filas.append(Tr(
            Td(c["texto"], cls="font-medium"), Td(c["n"]), Td(e["cursando"] + e["congelado"]),
            Td(egresaron), Td(e["titulado"]), Td(c["desertores"]),
            Td(_pct(cohortes.tasa(egresaron, c["n"]))), Td(_pct(cohortes.tasa(e["titulado"], c["n"]))),
            Td(_pct(cohortes.tasa(c["desertores"], c["n"])))))
    resumen = Div(
        *[Div(Div(str(v), cls="text-2xl font-semibold"), Div(t, cls=TextPresets.muted_sm), cls="rounded-md border border-border px-4 py-3")
          for v, t in ((ind["total"], "Estudiantes con cohorte"), (ind["estados"]["cursando"], "Cursando"),
                       (ind["estados"]["egresado"] + ind["estados"]["titulado"], "Egresados"),
                       (ind["estados"]["titulado"], "Titulados"), (ind["desertores"], "Desertores"),
                       ("—" if ind["anios_a_titulacion"] is None else f"{ind['anios_a_titulacion']:.1f}".replace(".", ","),
                        "Años medios hasta la titulación"))],
        cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6")
    cuerpo = (Table(Thead(Tr(Th("Cohorte"), Th("Ingresaron"), Th("Cursan"), Th("Egresaron"), Th("Titulados"),
                             Th("Desertores"), Th("Tasa de egreso"), Th("Tasa de titulación"), Th("Tasa de deserción"))),
                    Tbody(*filas), cls="uk-table-divider uk-table-middle", data_tabla="cohortes", data_tabla_filtro="no")
              if filas else P("Aún no hay estudiantes con cohorte. Cargue el CSV de Seguimiento Académico.",
                              cls=(TextPresets.muted_sm, "text-center py-6")))
    return resumen, Card(Div(cuerpo, cls="overflow-x-auto"))


@rt(BASE)
def get(auth):
    if not _puede_ver(auth):
        return Response("No autorizado", status_code=403)
    resumen, tabla = _tablero(auth)
    return pagina(
        "Cohortes estudiantiles",
        pestanas("cohortes", auth),
        Div(Div(H2("Cohortes estudiantiles"),
                P("Ingreso, egreso, titulación y deserción de la licenciatura por cohorte (semestre de ingreso). Son cifras "
                  "agregadas: no incluyen materias ni notas, que están en el sistema de Seguimiento Académico. Alimentan "
                  "las hojas 3 a 6 de la Guía de Antecedentes de IAC-CINDA.", cls=(TextPresets.muted_sm, "max-w-3xl"))),
            Button(UkIcon("upload", height=16, width=16), "Cargar CSV", cls=ButtonT.primary, hx_get=f"{BASE}/importar",
                   hx_target=f"#{ID_MODAL}") if _puede_cargar(auth) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        resumen, tabla,
        P("Solo cuenta a estudiantes de la licenciatura del programa propio con cohorte de ingreso. Un estudiante cuenta "
          "como matriculado desde su cohorte hasta su último ciclo matriculado; los congelamientos intermedios no se "
          "registran. Desertor: retirado, o congelado que no volvió en los dos ciclos siguientes (definición de IAC-CINDA). Las tasas son sobre los ingresantes de cada cohorte.", cls=(TextPresets.muted_sm, "mt-3 max-w-3xl")),
        usuario=auth, seccion="docencia")


# --- Carga del CSV ---------------------------------------------------------------------------------------------

def _formulario(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Suba el CSV exportado del sistema de Seguimiento Académico, con una fila por estudiante: ", Code("ru"), ", ",
          Code("nombres"), ", ", Code("apellidos"), ", ", Code("cohorte"), " (AAAA-I o AAAA-II) y ", Code("estado"),
          " (cursando, egresado, titulado, retirado o congelado). Opcionales: correo, sexo, fecha de nacimiento (solo "
          "se guarda la edad al ingresar), vía de ingreso, otra ciudad, extranjero, colegio, plan, último ciclo, "
          "fechas de egreso y titulación, modalidad y motivo del retiro.", cls="text-sm"),
        P("No suba materias ni notas. Los estudiantes que ya figuran (por RU, correo o nombre) se actualizan; los demás "
          "se registran. Primero verá una vista previa.", cls=TextPresets.muted_sm),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{BASE}/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
            Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_post=f"{BASE}/revisar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}", cls="space-y-4")


@rt(f"{BASE}/importar")
def get(auth):
    if not _puede_cargar(auth):
        return Response("No autorizado", status_code=403)
    return modal("Cargar cohortes", _formulario(), ancho="max-w-2xl")


@rt(f"{BASE}/plantilla")
def get(auth):
    if not _puede_cargar(auth):
        return Response("No autorizado", status_code=403)
    return Response(importar.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-cohortes.csv"'})


@rt(f"{BASE}/revisar")
async def post(auth, archivo: UploadFile = None):
    if not _puede_cargar(auth):
        return Response("No autorizado", status_code=403)
    if archivo is None or not archivo.filename:
        return modal("Cargar cohortes", _formulario(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar.MAX_BYTES + 1)
    filas, errores = importar.leer(contenido)
    if not filas:
        return modal("Cargar cohortes", _formulario(errores), ancho="max-w-2xl")
    listas = [f for f in filas if not f["errores"]]
    nuevas = sum(f["accion"] == "nueva" for f in listas)
    trs = []
    for f in filas:
        d = f["datos"]
        trs.append(Tr(
            Td(f["ru"], cls="text-sm"),
            Td(Div(f"{f['apellidos']}, {f['nombres']}", cls="font-medium"), Div(f["email"], cls=TextPresets.muted_sm)),
            Td(cohortes.texto(d["cohorte_anio"], d["cohorte_ciclo"]) if d.get("cohorte_anio") else "—", cls="text-sm"),
            Td(cohortes.ESTADOS.get(d["estado"], "—"), cls="text-sm"),
            Td(Label("Error", cls=LabelT.destructive), Div(*[P(e, cls="text-sm") for e in f["errores"]])
               if f["errores"] else
               Div(insignia("Nueva" if f["accion"] == "nueva" else "Actualiza", "azul" if f["accion"] == "nueva" else "gris"),
                   Div(f["aviso"] or "", cls=TextPresets.muted_sm)))))
    return modal(
        "Vista previa de las cohortes",
        P(f"{len(listas)} estudiante(s) se guardarán ({nuevas} nuevos) · {len(filas) - len(listas)} con errores, se omiten.",
          cls="text-sm font-medium mb-3"),
        Div(Table(Thead(Tr(Th("RU"), Th("Estudiante"), Th("Cohorte"), Th("Estado"), Th("Resultado"))), Tbody(*trs),
                  cls="uk-table-divider uk-table-small"), cls="max-h-96 overflow-y-auto border border-border rounded-md mb-4"),
        Form(Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button(f"Guardar {len(listas)} estudiante(s)", type="submit", cls=ButtonT.primary, disabled=not listas),
                 cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-5xl")


@rt(f"{BASE}/confirmar")
def post(auth, sess, contenido: str = ""):
    if not _puede_cargar(auth):
        return Response("No autorizado", status_code=403)
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return modal("Cargar cohortes", _formulario(["No se pudo leer el archivo. Súbalo otra vez."]))
    filas, _ = importar.leer(datos)
    nuevas, actualizadas = importar.aplicar(filas, auth["id"])
    add_toast(sess, f"Cohortes cargadas: {nuevas} nueva(s) y {actualizadas} actualizada(s).", "success")
    return Redirect(BASE)
