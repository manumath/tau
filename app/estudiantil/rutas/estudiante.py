"""Portal del estudiante (PLAN §49): su ficha, su participación en la investigación y su actividad estudiantil
declarada. Solo ve lo suyo: la ficha sale de su cuenta (`cuenta_estudiante`), nunca de la dirección.
Sin materias ni notas."""
from urllib.parse import quote

import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, FileResponse, Li, Option, P, Redirect, Response, Select, Span, Ul, UploadFile
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, FormLabel, LabelInput, TextPresets, UkIcon

from app.comun import estudiantes
from app.comun.componentes.layout import ID_MODAL, cerrar_modal, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar, get_db
from app.estudiantil import actividad, cohortes
from app.investigacion import adjuntos

rt = APIRouter()
BASE = "/estudiante"
ID_ACTIVIDADES = "actividades"
TONOS = {"pendiente": "ambar", "verificada": "verde", "observada": "rojo"}
CONSENTIMIENTO = ("TAU registra su trayectoria en la Carrera (cohorte, estado y plan) y la actividad que usted "
                  "declare aquí (ayudantías, olimpiadas, pasantías, becas, movilidad, semilleros y otras), con la "
                  "evidencia que adjunte. No registra sus materias ni sus notas: esas están en el sistema de "
                  "Seguimiento Académico. Los datos se usan para el seguimiento interno de la Carrera y, de forma "
                  "agregada (sin su nombre), como evidencia en los procesos de acreditación. Usted puede ver, "
                  "corregir y eliminar su actividad cuando quiera. La Dirección de Carrera, la Coordinación académica "
                  "y Gestión de datos pueden ver sus datos individuales; el Comité de acreditación solo ve cifras "
                  "agregadas.")


def _externo(auth) -> int | None:
    return estudiantes.cuenta_de(auth["id"])


def _sin_cuenta():
    return Response("Esta cuenta no es de estudiante.", status_code=403)


def _ficha(externo_id: int) -> dict:
    """Datos de la persona y de su periodo de licenciatura con cohorte (el más reciente)."""
    db = get_db()
    p = db.q("SELECT * FROM persona_externa WHERE id = ?", [externo_id])[0]
    e = db.q("""SELECT e.*, pl.nombre AS plan FROM estudiante e LEFT JOIN plan_estudios pl ON pl.id = e.plan_id
                WHERE e.externo_id = ? AND e.cohorte_anio IS NOT NULL ORDER BY e.desde DESC, e.id DESC LIMIT 1""",
             [externo_id])
    return {"persona": p, "periodo": e[0] if e else None}


# --- Página principal ----------------------------------------------------------------------------------------

def _fechas(a):
    return a["fecha_inicio"] + (f" a {a['fecha_fin']}" if a["fecha_fin"] else "")


def _fila_actividad(a):
    evidencias = [Li(A(UkIcon("paperclip", height=12, width=12), e["nombre"], href=f"{BASE}/evidencia/{e['id']}",
                       target="_blank", cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
                     fh.Button(UkIcon("x", height=12, width=12), type="button", aria_label=f"Quitar {e['nombre']}",
                               cls="ml-1 text-muted-foreground hover:text-foreground",
                               hx_delete=f"{BASE}/evidencia/{e['id']}", hx_target=f"#{ID_ACTIVIDADES}", hx_swap="outerHTML",
                               hx_confirm="¿Quitar esta evidencia? La actividad volverá a quedar por verificar."))
                  for e in a["evidencias"]]
    return Li(
        Div(Div(Span(a["titulo"], cls="font-medium"), insignia(actividad.ESTADOS[a["estado"]], TONOS[a["estado"]]),
                cls="flex flex-wrap items-center gap-2"),
            Div(f"{actividad.TIPOS[a['tipo']]} · {_fechas(a)}" + (f" · {a['institucion']}" if a["institucion"] else ""),
                cls=TextPresets.muted_sm),
            P(a["descripcion"], cls="text-sm") if a["descripcion"] else "",
            P(UkIcon("message-square", height=14, width=14, cls="shrink-0 mt-0.5"), Span(f"Observación: {a['observacion']}"),
              cls="flex items-start gap-1 text-sm text-red-700 dark:text-red-300") if a["observacion"] else "",
            Ul(*evidencias, cls="flex flex-wrap gap-3") if evidencias else "",
            cls="space-y-1 min-w-0"),
        Div(fh.Button(UkIcon("pencil", height=14, width=14), type="button", cls=(ButtonT.ghost, ButtonT.icon),
                      aria_label="Corregir", hx_get=f"{BASE}/actividades/{a['id']}/editar", hx_target=f"#{ID_MODAL}"),
            fh.Button(UkIcon("trash-2", height=14, width=14), type="button", cls=(ButtonT.ghost, ButtonT.icon),
                      aria_label="Eliminar", hx_delete=f"{BASE}/actividades/{a['id']}", hx_target=f"#{ID_ACTIVIDADES}",
                      hx_swap="outerHTML", hx_confirm="¿Eliminar esta actividad y su evidencia?"),
            cls="flex shrink-0"),
        cls="flex items-start justify-between gap-3 py-3")


def tarjeta_actividades(externo_id: int):
    filas = actividad.listar(externo_id)
    return Card(
        Div(H3("Mi actividad estudiantil", cls="text-base font-semibold"),
            Button(UkIcon("plus", height=16, width=16), "Registrar actividad", cls=(ButtonT.primary, ButtonT.sm),
                   hx_get=f"{BASE}/actividades/nueva", hx_target=f"#{ID_MODAL}"),
            cls="flex flex-wrap items-center justify-between gap-2 mb-1"),
        P("Ayudantías, olimpiadas, congresos, pasantías, becas, movilidad, semilleros y otras actividades. La Dirección "
          "de Carrera las verifica; puede adjuntar un certificado (PDF, PNG o JPG).", cls=(TextPresets.muted_sm, "mb-2")),
        Ul(*[_fila_actividad(a) for a in filas], cls="divide-y divide-border") if filas
        else P("Aún no registró actividades.", cls=(TextPresets.muted_sm, "py-4 text-center")),
        id=ID_ACTIVIDADES)


def _participacion(externo_id: int):
    part = estudiantes.participacion(externo_id)
    if not any(part.values()):
        return P("Aún no figura en tesis, publicaciones, proyectos ni actividades del instituto.", cls=TextPresets.muted_sm)

    def lista(titulo, items):
        return Div(H3(titulo, cls="text-sm font-semibold"),
                   Ul(*[Li(x[0], Span(x[1], cls=TextPresets.muted_sm), cls="text-sm") for x in items], cls="space-y-1 mt-1")
                   ) if items else ""
    return Div(
        lista("Tesis y publicaciones", [(x["titulo"], f" · {x['tipo']} · {x['anio']}") for x in part["productos"]]),
        lista("Proyectos", [(x["nombre"], f" · {x['rol']}") for x in part["proyectos"]]),
        lista("Actividades del instituto", [(x["titulo"], f" · {x['fecha_inicio']} · {x['rol']}") for x in part["actividades"]]),
        cls="space-y-3")


def _pagina_consentimiento(auth):
    return pagina(
        "Mi seguimiento",
        Div(Card(H2("Antes de empezar"),
                 P(CONSENTIMIENTO, cls="text-sm"),
                 Form(Button("Acepto el uso de mis datos", type="submit", cls=ButtonT.primary), method="post",
                      action=f"{BASE}/consentimiento", hx_post=f"{BASE}/consentimiento", hx_target="body",
                      cls="mt-4"),
                 cls="max-w-2xl space-y-3"), cls="flex justify-center"),
        usuario=auth, seccion="estudiante")


def _tarjeta_apoyo(externo: int):
    """Tutor(a) del estudiante y enlaces al directorio de egresados (estudiantes) o a su perfil (egresados)."""
    tutor = estudiantes.tutor_de(externo)
    egresado = estudiantes.es_egresado(externo)
    contenido = []
    if tutor:
        contenido.append(P(Span("Su tutor(a): ", cls="font-medium"), f"{tutor['nombres']} {tutor['apellidos']} · {tutor['email']}", cls="text-sm"))
    contenido.append(A(UkIcon("book-user", height=14, width=14), "Directorio de egresados", href=f"{BASE}/directorio",
                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"))
    if egresado:
        contenido.append(A(UkIcon("id-card", height=14, width=14), "Mi perfil de egresado", href=f"{BASE}/perfil-egresado",
                           cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"))
    return Card(H3("Apoyo y comunidad", cls="text-base font-semibold mb-2"), Div(*contenido, cls="flex flex-col gap-2"))


@rt(BASE)
def get(auth):
    externo = _externo(auth)
    if externo is None:
        return _sin_cuenta()
    if not estudiantes.consintio(externo):
        return _pagina_consentimiento(auth)
    f = _ficha(externo)
    p, e = f["persona"], f["periodo"]
    datos = [f"RU {e['registro_universitario']}" if e and e["registro_universitario"] else None,
             f"Cohorte {cohortes.texto(e['cohorte_anio'], e['cohorte_ciclo'])}" if e else None,
             e["plan"] if e else None, cohortes.ESTADOS[e["estado"]] if e else None]
    return pagina(
        "Mi seguimiento",
        H2(f"{p['nombres']} {p['apellidos']}"),
        P(" · ".join(x for x in datos if x) or "Sin datos de cohorte todavía.", cls=(TextPresets.muted_sm, "mb-6")),
        Div(tarjeta_actividades(externo),
            Div(Card(H3("Mi participación en la investigación", cls="text-base font-semibold mb-2"), _participacion(externo)),
                _tarjeta_apoyo(externo), cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        P("TAU no registra sus materias ni sus notas. Si algún dato de arriba no es correcto, avise a la Dirección de Carrera.",
          cls=(TextPresets.muted_sm, "mt-6")),
        usuario=auth, seccion="estudiante")


@rt(f"{BASE}/consentimiento")
def post(auth, sess):
    externo = _externo(auth)
    if externo is None:
        return _sin_cuenta()
    if not estudiantes.consintio(externo):
        estudiantes.aceptar_consentimiento(externo)
        auditar(auth["id"], "aceptar_consentimiento_estudiantil", "persona_externa", externo)
    return Redirect(BASE)


# --- Actividades ------------------------------------------------------------------------------------------------

def _form(d=None, errores=(), aid=None):
    d = d or {}
    destino = f"{BASE}/actividades" + (f"/{aid}" if aid else "")
    return modal(
        "Corregir actividad" if aid else "Registrar actividad",
        Form(mensaje_error(*errores),
             Div(FormLabel("Tipo"), Select(Option("— Elija —", value=""),
                                          *[Option(t, value=k, selected=k == d.get("tipo")) for k, t in actividad.TIPOS.items()],
                                          name="tipo", cls="uk-select", required=True), cls="space-y-1"),
             LabelInput("Título", id="titulo", value=d.get("titulo") or "", required=True, maxlength="200",
                        placeholder="Ayudantía de Cálculo I, Olimpiada Nacional de Matemática…"),
             LabelInput("Institución o lugar (opcional)", id="institucion", value=d.get("institucion") or ""),
             Div(LabelInput("Desde", id="fecha_inicio", type="date", value=d.get("fecha_inicio") or "", required=True),
                 LabelInput("Hasta (opcional)", id="fecha_fin", type="date", value=d.get("fecha_fin") or ""),
                 cls="grid grid-cols-2 gap-3"),
             Div(FormLabel("Descripción (opcional)"),
                 fh.Textarea(d.get("descripcion") or "", name="descripcion", rows="3", maxlength="2000", cls="uk-textarea"),
                 cls="space-y-1"),
             Div(FormLabel("Evidencia (opcional)"),
                 fh.Input(type="file", name="archivo", accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg",
                          aria_label="Evidencia"),
                 P("PDF, PNG o JPG de hasta 20 MB: un certificado, una constancia…" +
                   (" Los archivos ya adjuntos se quitan desde la lista." if aid else ""), cls=TextPresets.muted_sm),
                 cls="space-y-1"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=destino, hx_target=f"#{ID_MODAL}", hx_encoding="multipart/form-data", cls="space-y-4"),
        ancho="max-w-xl")


def _requiere(auth):
    """→ (ficha, None) si es estudiante y ya aceptó; si no, (None, respuesta)."""
    externo = _externo(auth)
    if externo is None:
        return None, _sin_cuenta()
    if not estudiantes.consintio(externo):
        return None, Response("Primero acepte el uso de sus datos.", status_code=403)
    return externo, None


def _propia(externo, aid):
    a = actividad.obtener(aid)
    return a if a and a["externo_id"] == externo else None


@rt(f"{BASE}/actividades/nueva")
def get(auth):
    externo, error = _requiere(auth)
    return error or _form()


@rt(f"{BASE}/actividades/{{aid}}/editar")
def get(auth, aid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    a = _propia(externo, aid)
    return _form(a, aid=aid) if a else Response("No encontrada", status_code=404)


async def _guardar(auth, aid, d, archivo):
    """Crea (aid None) o corrige una actividad propia, con su evidencia. → respuesta."""
    externo, error = _requiere(auth)
    if error:
        return error
    if aid is not None and not _propia(externo, aid):
        return Response("No encontrada", status_code=404)
    contenido = await archivo.read(adjuntos.MAX_BYTES + 1) if archivo is not None and archivo.filename else b""
    problemas = []
    if contenido and not adjuntos.detectar_tipo(contenido):
        problemas.append("La evidencia debe ser un archivo PDF, PNG o JPG.")
    elif len(contenido) > adjuntos.MAX_BYTES:
        problemas.append("La evidencia supera los 20 MB.")
    _, errores = actividad.validar(d)
    if errores or problemas:
        return _form(d, [*errores, *problemas], aid)
    if aid is None:
        aid, _ = actividad.crear(externo, d)
    else:
        actividad.editar(aid, d)
    if contenido:
        try:
            adjuntos.guardar(actividad.ENTIDAD, aid, archivo.filename, contenido, auth["id"])
        except ValueError as e:
            actividad.marcar_pendiente(aid)
            return _form(d, [str(e)], aid)
        actividad.marcar_pendiente(aid)
    auditar(auth["id"], "registrar_actividad_estudiantil", actividad.ENTIDAD, aid, d.get("titulo"))
    return tarjeta_actividades(externo), cerrar_modal()


@rt(f"{BASE}/actividades")
async def post(auth, tipo: str = "", titulo: str = "", institucion: str = "", fecha_inicio: str = "", fecha_fin: str = "",
               descripcion: str = "", archivo: UploadFile = None):
    d = dict(tipo=tipo, titulo=titulo, institucion=institucion, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
             descripcion=descripcion)
    return await _guardar(auth, None, d, archivo)


@rt(f"{BASE}/actividades/{{aid}}")
async def post(auth, aid: int, tipo: str = "", titulo: str = "", institucion: str = "", fecha_inicio: str = "",
               fecha_fin: str = "", descripcion: str = "", archivo: UploadFile = None):
    d = dict(tipo=tipo, titulo=titulo, institucion=institucion, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
             descripcion=descripcion)
    return await _guardar(auth, aid, d, archivo)


@rt(f"{BASE}/actividades/{{aid}}")
def delete(auth, aid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    if not _propia(externo, aid):
        return Response("No encontrada", status_code=404)
    actividad.eliminar(aid)
    auditar(auth["id"], "eliminar_actividad_estudiantil", actividad.ENTIDAD, aid)
    return tarjeta_actividades(externo)


# --- Evidencia ------------------------------------------------------------------------------------------------

def respuesta_evidencia(adj):
    return FileResponse(adjuntos.ruta(adj), media_type=adj["mime"], headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(adj['nombre'])}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


def _evidencia_propia(externo, adj_id):
    adj = adjuntos.obtener(adj_id)
    if not adj or adj["entidad"] != actividad.ENTIDAD or not _propia(externo, adj["entidad_id"]):
        return None
    return adj


@rt(f"{BASE}/evidencia/{{adj_id}}")
def get(auth, adj_id: int):
    externo, error = _requiere(auth)
    if error:
        return error
    adj = _evidencia_propia(externo, adj_id)
    return respuesta_evidencia(adj) if adj else Response("No encontrada", status_code=404)


@rt(f"{BASE}/evidencia/{{adj_id}}")
def delete(auth, adj_id: int):
    externo, error = _requiere(auth)
    if error:
        return error
    adj = _evidencia_propia(externo, adj_id)
    if not adj:
        return Response("No encontrada", status_code=404)
    adjuntos.eliminar(adj)
    actividad.marcar_pendiente(adj["entidad_id"])
    auditar(auth["id"], "quitar_evidencia_estudiantil", actividad.ENTIDAD, adj["entidad_id"], adj["nombre"])
    return tarjeta_actividades(externo)
