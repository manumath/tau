"""Convenios (PLAN §57, etapa 8): los registra la Dirección de Carrera, con sus actividades; los ven quienes ven el marco
de calidad."""
from fasthtml.common import A, APIRouter, Div, Li, P, Redirect, Response, Span, Table, Tbody, Td, Th, Thead, Tr, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, LabelInput, LabelTextArea, TextPresets, UkIcon

from app.calidad import convenios, evidencias, marco
from app.calidad.rutas.mejora import _botones_modal, _dato, _fecha, _select
from app.comun import unidades
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/calidad/convenios"


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _no():
    return Response("No autorizado", status_code=403)


def _ve(auth, m):
    return marco.puede(auth, "ver_marco_calidad", m)


def _registra(auth, m):
    return marco.puede(auth, "registrar_convenios", m)


def _estado(v):
    return insignia("Vigente", "verde") if v["vigente"] else insignia("Vencido", "gris")


@rt(BASE)
def get(auth):
    m = _marco()
    if not _ve(auth, m):
        return _no()
    lista = convenios.listar()
    return pagina(
        "Convenios",
        Div(H2("Convenios"),
            Button(UkIcon("plus", height=14, width=14), "Registrar convenio", cls=(ButtonT.primary, ButtonT.sm),
                   hx_get=f"{BASE}/nuevo", hx_target=f"#{ID_MODAL}") if _registra(auth, m) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-2"),
        P("Convenios de la Carrera con universidades, centros de investigación, organismos y empresas, y lo que se hizo con "
          "cada uno (estancias, cursos, proyectos, publicaciones, eventos). Alimentan el indicador «Convenios con actividad "
          "en el año».", cls="text-sm max-w-3xl mb-4"),
        Div(Table(Thead(Tr(Th("Contraparte"), Th("Ámbito", cls="w-28"), Th("Tipo", cls="w-24"), Th("Firma", cls="w-24"),
                           Th("Hasta", cls="w-24"), Th("Actividades", cls="w-28 text-right"), Th("Estado", cls="w-24"))),
                  Tbody(*[Tr(Td(A(v["contraparte"], href=f"{BASE}/{v['id']}", cls="font-medium hover:underline"),
                                Div(v["pais"] or "", cls=TextPresets.muted_sm)),
                             Td(convenios.AMBITOS[v["ambito"]]), Td(convenios.TIPOS[v["tipo"]]), Td(_fecha(v["fecha_firma"])),
                             Td(_fecha(v["vigente_hasta"]) if v["vigente_hasta"] else "Indefinido"),
                             Td(str(v["actividades"]), Div(f"última: {_fecha(v['ultima'])}", cls=TextPresets.muted_sm)
                                if v["ultima"] else "", cls="text-right"),
                             Td(_estado(v))) for v in lista]),
                  cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[48rem]"), cls="overflow-x-auto")
        if lista else P("Aún no hay convenios registrados.", cls=TextPresets.muted_sm),
        usuario=auth)


def _form(m, d, url, metodo, errores=()):
    def v(k):
        return d.get(k) if d.get(k) is not None else ""
    evs = [(e["id"], e["titulo"]) for e in evidencias.listar(m["id"])]
    return modal(
        "Convenio",
        Form(mensaje_error(*errores),
             Div(Div(LabelInput("Institución contraparte", id="contraparte", value=v("contraparte"), required=True,
                                maxlength=300), cls="sm:col-span-2"),
                 LabelInput("País (opcional)", id="pais", value=v("pais"), maxlength=100),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
             Div(_select("Ámbito", "ambito", list(convenios.AMBITOS.items()), v("ambito") or "nacional"),
                 _select("Tipo", "tipo", list(convenios.TIPOS.items()), v("tipo") or "marco"),
                 LabelInput("Firma", id="fecha_firma", type="date", value=v("fecha_firma"), required=True),
                 LabelInput("Vigente hasta (vacío: indefinido)", id="vigente_hasta", type="date", value=v("vigente_hasta")),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             LabelTextArea("Objeto (opcional)", id="objeto", value=v("objeto"), rows=2),
             _select("Texto firmado (evidencia del repositorio, opcional)", "evidencia_id", evs, v("evidencia_id"), "—"),
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-2xl")


def _datos(f):
    return {k: f.get(k, "") for k in convenios.CAMPOS}


def _validos(m):
    return {e["id"] for e in evidencias.listar(m["id"])}


@rt(f"{BASE}/nuevo")
def get(auth):
    m = _marco()
    return _form(m, {}, BASE, "post") if _registra(auth, m) else _no()


@rt(BASE)
async def post(auth, sess, req):
    m = _marco()
    if not _registra(auth, m):
        return _no()
    x, errores = convenios.validar(_datos(await req.form()), _validos(m))
    if errores:
        return _form(m, x, BASE, "post", errores)
    vid = convenios.crear(x, auth["id"])
    auditar(auth["id"], "registrar_convenio", "convenio", vid, x["contraparte"])
    add_toast(sess, "Convenio registrado.", "success")
    return Redirect(f"{BASE}/{vid}")


def form_actividad(vid, d=None, errores=()):
    d = d or {}
    return Form(mensaje_error(*errores),
                Div(LabelInput("Fecha", id="fecha", type="date", value=d.get("fecha") or "", required=True),
                    Div(LabelInput("Actividad", id="descripcion", value=d.get("descripcion") or "", required=True,
                                   maxlength=2000, placeholder="Por ejemplo: estancia de un docente, curso conjunto, artículo"),
                        cls="sm:col-span-3"),
                    cls="grid grid-cols-1 sm:grid-cols-4 gap-4"),
                Div(Button("Agregar actividad", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end"),
                hx_post=f"{BASE}/{vid}/actividades", hx_target="#form-actividad", hx_select="#form-actividad",
                hx_swap="outerHTML", id="form-actividad", cls="space-y-3 mt-4")


@rt(f"{BASE}/{{vid}}")
def get(auth, vid: int):
    m, v = _marco(), convenios.obtener(vid)
    if not _ve(auth, m):
        return _no()
    if v is None:
        return Response("No encontrado", status_code=404)
    registra = _registra(auth, m)
    url = f"{BASE}/{vid}"
    return pagina(
        v["contraparte"],
        A(UkIcon("arrow-left", height=14, width=14), "Convenios", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(Div(H2(v["contraparte"]), Div(_estado(v), cls="mt-2")),
            Div(Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"{url}/editar", hx_target=f"#{ID_MODAL}"),
                Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
                       hx_delete=url, hx_target="body", hx_confirm="¿Eliminar el convenio?")
                if not v["lista_actividades"] else "",
                cls="flex gap-2") if registra else "",
            cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(Div(Div(_dato("País", v["pais"] or "—"), _dato("Ámbito", convenios.AMBITOS[v["ambito"]]),
                     _dato("Tipo", convenios.TIPOS[v["tipo"]]), cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 Div(_dato("Firma", _fecha(v["fecha_firma"])),
                     _dato("Vigente hasta", _fecha(v["vigente_hasta"]) if v["vigente_hasta"] else "Indefinido"),
                     _dato("Texto firmado", A(v["evidencia_titulo"], href=f"/calidad/evidencias/{v['evidencia_id']}",
                                              cls="text-primary hover:underline") if v["evidencia_id"] else "—"),
                     cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 _dato("Objeto", v["objeto"] or "—"), cls="space-y-4")),
        Card(H3("Actividades", cls="text-base font-semibold mb-2"),
             Ul(*[Li(Div(Span(_fecha(a["fecha"]), cls="font-medium"), Span(f" · {a['por']}", cls=TextPresets.muted_sm)
                         if a["por"] else "",
                         Button(UkIcon("trash-2", height=12, width=12), cls=(ButtonT.ghost, ButtonT.xs), type="button",
                                aria_label="Quitar la actividad", title="Quitar la actividad",
                                hx_delete=f"{url}/actividades/{a['id']}", hx_target="body",
                                hx_confirm="¿Quitar esta actividad?") if registra else ""),
                     P(a["descripcion"], cls="text-sm"), cls="space-y-1 pt-3") for a in v["lista_actividades"]],
                cls="divide-y divide-border space-y-3") if v["lista_actividades"] else
             P("Aún sin actividades registradas.", cls=TextPresets.muted_sm),
             form_actividad(vid) if registra else "", cls="mt-6"),
        usuario=auth)


@rt(f"{BASE}/{{vid}}/editar")
def get(auth, vid: int):
    m, v = _marco(), convenios.obtener(vid)
    if not _registra(auth, m):
        return _no()
    return _form(m, v, f"{BASE}/{vid}", "put") if v else Response("No encontrado", status_code=404)


@rt(f"{BASE}/{{vid}}")
async def put(auth, sess, req, vid: int):
    m, v = _marco(), convenios.obtener(vid)
    if not _registra(auth, m):
        return _no()
    if v is None:
        return Response("No encontrado", status_code=404)
    x, errores = convenios.validar(_datos(await req.form()), _validos(m))
    if errores:
        return _form(m, x, f"{BASE}/{vid}", "put", errores)
    convenios.actualizar(vid, x)
    auditar(auth["id"], "editar_convenio", "convenio", vid, x["contraparte"])
    add_toast(sess, "Convenio guardado.", "success")
    return Redirect(f"{BASE}/{vid}")


@rt(f"{BASE}/{{vid}}")
def delete(auth, sess, vid: int):
    m, v = _marco(), convenios.obtener(vid)
    if not _registra(auth, m):
        return _no()
    if v is None:
        return Response("No encontrado", status_code=404)
    if not convenios.eliminar(v):
        add_toast(sess, "El convenio tiene actividades: no se puede eliminar.", "error")
        return Redirect(f"{BASE}/{vid}")
    auditar(auth["id"], "eliminar_convenio", "convenio", vid, v["contraparte"])
    add_toast(sess, "Convenio eliminado.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{vid}}/actividades")
def post(auth, sess, vid: int, fecha: str = "", descripcion: str = ""):
    m, v = _marco(), convenios.obtener(vid)
    if not _registra(auth, m):
        return _no()
    if v is None:
        return Response("No encontrado", status_code=404)
    x, errores = convenios.validar_actividad({"fecha": fecha, "descripcion": descripcion})
    if errores:
        return form_actividad(vid, x, errores)
    convenios.agregar_actividad(vid, x, auth["id"])
    auditar(auth["id"], "actividad_convenio", "convenio", vid, x["descripcion"][:80])
    add_toast(sess, "Actividad agregada.", "success")
    return Redirect(f"{BASE}/{vid}")


@rt(f"{BASE}/{{vid}}/actividades/{{aid}}")
def delete(auth, sess, vid: int, aid: int):
    m, a = _marco(), convenios.actividad(aid)
    if not _registra(auth, m):
        return _no()
    if a is None or a["convenio_id"] != vid:
        return Response("No encontrada", status_code=404)
    convenios.quitar_actividad(aid)
    auditar(auth["id"], "quitar_actividad_convenio", "convenio", vid, a["descripcion"][:80])
    add_toast(sess, "Actividad quitada.", "success")
    return Redirect(f"{BASE}/{vid}")
