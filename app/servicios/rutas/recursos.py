"""Biblioteca y recursos (PLAN §67, etapa 10): los docentes suben apuntes, guías, exámenes pasados, libros y enlaces por asignatura
(/servicios/recursos); los estudiantes los buscan y descargan (/estudiante/biblioteca)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Redirect, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import formato
from app.comun.componentes.layout import campo, mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.estudiantil.rutas.estudiante import _requiere
from app.investigacion import adjuntos
from app.academico import oferta
from app.servicios import recursos
from app.servicios.rutas.comun import descargar, leer_archivo, no_autorizado, no_encontrado

rt = APIRouter()
BASE = "/servicios/recursos"
EST = "/estudiante/biblioteca"


def _asignaturas():
    return oferta.asignaturas_ofertables()


# --- Docentes -----------------------------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    if not recursos.puede_publicar(auth):
        return no_autorizado()
    lista = recursos.mis_recursos(auth)
    return pagina(
        "Recursos", H2("Biblioteca y recursos"),
        P("Suba apuntes, guías, exámenes pasados, libros o enlaces para los estudiantes, por asignatura. Suba solo material propio o "
          "que tenga permiso de compartir.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        A(UkIcon("plus", height=14, width=14), "Subir un recurso", href=f"{BASE}/nuevo", cls="uk-btn uk-btn-primary gap-1 mb-4"),
        Card(Ul(*[Li(Div(Span(r["titulo"], cls="font-medium"), insignia(recursos.TIPOS[r["tipo"]], "azul"),
                         insignia("Retirado", "gris") if r["estado"] == "retirado" else "", cls="flex flex-wrap items-center gap-2"),
                     P(f"{r['nombres']} {r['apellidos']} · " + ", ".join(a["sigla"] for a in recursos.asignaturas_de(r["id"])),
                       cls=TextPresets.muted_sm),
                     fh.Form(Button("Retirar", type="button", hx_post=f"{BASE}/{r['id']}/retirar", hx_swap="none",
                                    hx_confirm="¿Retirar este recurso? Los estudiantes ya no lo verán.", cls=(ButtonT.ghost, ButtonT.xs)))
                     if r["estado"] == "publicado" else "", cls="py-3") for r in lista], cls="divide-y divide-border"))
        if lista else P("Todavía no subió recursos.", cls=TextPresets.muted_sm), usuario=auth)


def _form(errores=(), v=None):
    v = v or {}
    elegidas = {str(x) for x in v.get("asignaturas", [])}
    return fh.Form(
        mensaje_error(*errores),
        Div(campo("Tipo", Select(*[Option(t, value=k, selected=v.get("tipo") == k) for k, t in recursos.TIPOS.items()], name="tipo",
                                 cls="uk-select")),
            campo("Año (exámenes pasados)", Input(name="anio", value=v.get("anio", ""), inputmode="numeric", cls="uk-input")),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        campo("Título", Input(name="titulo", value=v.get("titulo", ""), required=True, maxlength="200", cls="uk-input")),
        campo("Descripción", fh.Textarea(v.get("descripcion", ""), name="descripcion", rows=3, cls="uk-textarea")),
        campo("Asignaturas (una o varias)", Select(*[Option(f"{a['sigla']} · {a['nombre']}", value=str(a["id"]),
                                                            selected=str(a["id"]) in elegidas) for a in _asignaturas()],
                                                   name="asignaturas", multiple=True, size="8", cls="uk-select")),
        Div(campo("Archivo (PDF, PNG o JPG, hasta 20 MB)", Input(type="file", name="archivo", accept=".pdf,.png,.jpg,.jpeg",
                                                                  cls="text-sm w-full")),
            campo("o un enlace", Input(name="enlace", value=v.get("enlace", ""), placeholder="https://", cls="uk-input")),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        Div(Button("Subir", type="submit", cls=ButtonT.primary), A("Cancelar", href=BASE, cls="uk-btn uk-btn-ghost"),
            cls="flex gap-2"), method="post", action=BASE, enctype="multipart/form-data", cls="space-y-3")


@rt(f"{BASE}/nuevo")
def get(auth):
    if not recursos.puede_publicar(auth):
        return no_autorizado()
    return pagina("Subir un recurso", H2("Subir un recurso"), Card(_form()), usuario=auth)


@rt(BASE)
async def post(auth, sess, req):
    if not recursos.puede_publicar(auth):
        return no_autorizado()
    f = await req.form()
    d = {k: f.get(k, "") for k in ("tipo", "titulo", "descripcion", "enlace", "anio")}
    archivo = f.get("archivo")
    contenido, nombre = b"", ""
    if archivo is not None and getattr(archivo, "filename", ""):
        contenido, error = await leer_archivo(archivo)
        if error:
            return pagina("Subir un recurso", H2("Subir un recurso"), Card(_form([error], {**d, "asignaturas": f.getlist("asignaturas")})),
                          usuario=auth)
        nombre = archivo.filename
    rid, errores = recursos.crear(d, f.getlist("asignaturas"), auth, (contenido, nombre) if contenido else None)
    if errores:
        return pagina("Subir un recurso", H2("Subir un recurso"), Card(_form(errores, {**d, "asignaturas": f.getlist("asignaturas")})),
                      usuario=auth)
    add_toast(sess, "Recurso publicado: los estudiantes ya lo ven.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{rid}}/retirar")
def post(auth, sess, rid: int):
    r = recursos.obtener(rid)
    if not r:
        return no_encontrado()
    errores = recursos.retirar(rid, auth)
    add_toast(sess, errores[0] if errores else "Recurso retirado.", "error" if errores else "success")
    return Redirect(BASE)


# --- Estudiantes ----------------------------------------------------------------------------------------------------------------

@rt(EST)
def get(auth, q: str = "", asignatura: str = "", tipo: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    lista = recursos.buscar(q, asignatura, tipo)
    return pagina(
        "Biblioteca", H2("Biblioteca y recursos"),
        P("Apuntes, guías de ejercicios, exámenes pasados y otros materiales que suben los docentes, por asignatura.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        fh.Form(Input(name="q", value=q, placeholder="Buscar por título, asignatura o docente", aria_label="Buscar", cls="uk-input"),
                Select(Option("Todas las asignaturas", value=""), *[Option(f"{a['sigla']} · {a['nombre']}", value=str(a["id"]),
                                                                          selected=str(a["id"]) == asignatura) for a in _asignaturas()],
                       name="asignatura", aria_label="Asignatura", cls="uk-select"),
                Select(Option("Todos los tipos", value=""), *[Option(t, value=k, selected=k == tipo) for k, t in recursos.TIPOS.items()],
                       name="tipo", aria_label="Tipo", cls="uk-select"),
                Button("Buscar", type="submit", cls=ButtonT.default), method="get", cls="grid grid-cols-1 sm:grid-cols-4 gap-2 mb-4"),
        Div(*[Card(Div(insignia(recursos.TIPOS[r["tipo"]], "azul"), Span(str(r["anio"]) if r["anio"] else "", cls=TextPresets.muted_sm),
                       cls="flex items-center gap-2"),
                   Span(r["titulo"], cls="font-medium block mt-1"),
                   P(r["descripcion"] or "", cls="text-sm"),
                   P(", ".join(f"{a['sigla']}" for a in r["asignaturas"]) + f" · {r['nombres']} {r['apellidos']} · "
                     + formato.fecha(r["creado_en"][:10]), cls=TextPresets.muted_sm),
                   Div(*[A(UkIcon("download", height=14, width=14), x["nombre"], href=f"{EST}/{r['id']}/archivo/{x['id']}",
                           cls="inline-flex items-center gap-1 text-sm text-primary hover:underline") for x in recursos.archivos(r["id"])],
                       A(UkIcon("external-link", height=14, width=14), "Abrir el enlace", href=r["enlace"], target="_blank",
                         rel="noopener noreferrer", cls="inline-flex items-center gap-1 text-sm text-primary hover:underline")
                       if r["enlace"] else "", cls="flex flex-wrap gap-3 mt-2")) for r in lista], cls="grid grid-cols-1 md:grid-cols-2 gap-3")
        if lista else Card(P("No hay recursos con esos criterios.", cls="text-sm")), usuario=auth)


@rt(f"{EST}/{{rid}}/archivo/{{aid}}")
def get(auth, rid: int, aid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    r = recursos.obtener(rid)
    adj = adjuntos.obtener(aid)
    if not r or r["estado"] != "publicado" or not adj or adj["entidad"] != "recurso" or adj["entidad_id"] != rid:
        return no_encontrado()
    return descargar(adj, adjunto=True)


@rt(f"{BASE}/{{rid}}/archivo/{{aid}}")
def get(auth, rid: int, aid: int):
    r = recursos.obtener(rid)
    adj = adjuntos.obtener(aid)
    if not r or not recursos.puede_gestionar(auth, r) or not adj or adj["entidad"] != "recurso" or adj["entidad_id"] != rid:
        return no_autorizado()
    return descargar(adj, adjunto=True)
