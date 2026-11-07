"""Marco de calidad de la Carrera (PLAN §57, etapa 2): ver el marco por dimensión, filtrarlo por atributo, editarlo
(Dirección de Carrera) y exportarlo en XLSX. Lo ven también la Coordinación académica, la Dirección del Instituto y la
Comisión de calidad (`ver_marco_calidad`)."""
from fasthtml.common import (A, APIRouter, Div, Label, Li, Option, P, Redirect, Response, Select, Span, Table,
                             Tbody, Td, Th, Thead, Tr, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, H3, H4, Button, ButtonT, Card, CheckboxX, Form, FormLabel, LabelInput, LabelTextArea,
                           TextPresets, UkIcon)

from app.calidad import evidencias, indicadores, marco, publico
from app.calidad.rutas.indicadores import cifra, numero
from app.calidad.rutas.informes import XLSX, _archivo, descarga
from app.comun import permisos, unidades
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/calidad/marco"


def _no_autorizado():
    return Response("No autorizado", status_code=403)


def _no_encontrado():
    return Response("No encontrado", status_code=404)


def _unidad():
    return unidades.id_de("CMAT")   # un marco por unidad; se empieza por la Carrera (decisión 5)


_puede = marco.puede


def _boton(icono, etiqueta, **kw):
    return Button(UkIcon(icono, height=14, width=14), cls=(ButtonT.ghost, ButtonT.sm), type="button",
                  aria_label=etiqueta, title=etiqueta, **kw)


def _acciones(gestiona, *botones):
    return Div(*botones, cls="flex shrink-0 items-start") if gestiona else ""


def _fecha(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else None


def _vigencia(m):
    desde, hasta = _fecha(m["vigente_desde"]), _fecha(m["vigente_hasta"])
    if desde and hasta:
        return f"vigente del {desde} al {hasta}"
    if desde:
        return f"vigente desde el {desde}"
    return f"vigente hasta el {hasta}" if hasta else "sin fecha de vigencia (borrador)"


def _insignia_fuente(i):
    return (insignia("Automático", "azul", titulo=marco.fuente_texto(i["fuente"]), icono="cpu")
            if i["fuente"].startswith("auto:") else insignia("Manual", "gris", titulo=marco.fuente_texto(i["fuente"])))


# --- Pantalla principal --------------------------------------------------------------------------------------

def _tabla_indicadores(c, gestiona):
    if not c["indicadores"]:
        return P("Sin indicadores.", cls=TextPresets.muted_sm)
    return Div(Table(
        Thead(Tr(Th("Código", cls="w-24"), Th("Indicador"), Th("Tipo", cls="w-28"), Th("Fuente", cls="w-32"),
                 Th("Frecuencia", cls="w-32"), Th("Metas", cls="w-20"))),
        Tbody(*[Tr(Td(A(i["codigo"], href=f"{BASE}/indicadores/{i['id']}", cls="font-mono hover:underline")),
                   Td(i["nombre"], " ", insignia("Inactivo", "gris") if not i["activo"] else "",
                      " ", insignia("Público", "verde", icono="globe") if i["publico"] else ""),
                   Td(marco.TIPOS[i["tipo"]]), Td(_insignia_fuente(i)), Td(marco.FRECUENCIAS[i["frecuencia"]]),
                   Td(", ".join(str(mt["anio"]) for mt in i["metas"]) or "—"),
                   cls="" if i["activo"] else "opacity-60")
                for i in c["indicadores"]]),
        cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[40rem]"), cls="overflow-x-auto")


def _criterio(c, gestiona, mid):
    return Div(
        Div(Div(H4(Span(c["codigo"], cls="font-mono mr-2"), c["nombre"], cls="text-sm font-semibold"),
                P(c["descripcion"], cls=TextPresets.muted_sm) if c["descripcion"] else "",
                A(UkIcon("folder-open", height=12, width=12),
                  f" {c['evidencias']} evidencia{'s' if c['evidencias'] != 1 else ''} vigente"
                  f"{'s' if c['evidencias'] != 1 else ''}", href=f"/calidad/evidencias?criterio={c['id']}",
                  cls="inline-flex items-center gap-1 text-xs text-primary hover:underline")
                if c.get("evidencias") is not None else "", cls="flex-1"),
            _acciones(gestiona,
                      _boton("plus", "Agregar indicador", hx_get=f"{BASE}/criterios/{c['id']}/indicadores/nuevo",
                             hx_target=f"#{ID_MODAL}"),
                      _boton("pencil", "Editar criterio", hx_get=f"{BASE}/criterios/{c['id']}/editar",
                             hx_target=f"#{ID_MODAL}"),
                      _boton("trash-2", "Eliminar criterio", hx_delete=f"{BASE}/criterios/{c['id']}",
                             hx_confirm=f"¿Eliminar el criterio {c['codigo']}?")
                      if not c["indicadores"] and not c.get("evidencias") else ""),
            cls="flex gap-3"),
        _tabla_indicadores(c, gestiona), cls="space-y-2 pt-4", id=f"criterio-{c['id']}")


def _dimension(d, gestiona, mid):
    return Card(
        Div(Div(H3(Span(d["codigo"], cls="font-mono mr-2"), d["nombre"], cls="text-lg font-semibold"),
                P(d["descripcion"], cls="text-sm mt-1") if d["descripcion"] else "",
                P("Se alinea con: ", d["referencia"], cls=(TextPresets.muted_sm, "mt-1")) if d["referencia"] else "",
                cls="flex-1"),
            _acciones(gestiona,
                      _boton("plus", "Agregar criterio", hx_get=f"{BASE}/dimensiones/{d['id']}/criterios/nuevo",
                             hx_target=f"#{ID_MODAL}"),
                      _boton("pencil", "Editar dimensión", hx_get=f"{BASE}/dimensiones/{d['id']}/editar",
                             hx_target=f"#{ID_MODAL}"),
                      _boton("trash-2", "Eliminar dimensión", hx_delete=f"{BASE}/dimensiones/{d['id']}",
                             hx_confirm=f"¿Eliminar la dimensión {d['codigo']}?") if not d["criterios"] else ""),
            cls="flex gap-3"),
        Div(*[_criterio(c, gestiona, mid) for c in d["criterios"]], cls="divide-y divide-border")
        if d["criterios"] else P("Sin criterios.", cls=(TextPresets.muted_sm, "mt-2")),
        id=f"dimension-{d['id']}")


def _filtro_atributos(mid, actual):
    def chip(texto, clave):
        activo = clave == actual
        return A(texto, href=f"{BASE}?atributo={clave}" if clave else BASE,
                 aria_current="true" if activo else None,
                 cls="text-xs rounded px-2 py-1 " + ("bg-primary text-primary-foreground" if activo else
                                                     "bg-muted hover:bg-muted/70"))
    return Div(P("Ver solo los indicadores que dan evidencia de un atributo (criterios de calidad de la UMSA):",
                 cls=(TextPresets.muted_sm, "mb-2")),
               Div(chip("Todos", ""), *[chip(a["nombre"], a["clave"]) for a in marco.atributos(mid)],
                   cls="flex flex-wrap gap-1"), cls="mb-6")


@rt(BASE)
def get(auth, atributo: str = ""):
    m = marco.de_unidad(_unidad())
    if m is None:
        return pagina("Marco de calidad", H2("Marco de calidad"),
                      P("La Carrera aún no tiene un marco de calidad.", cls=TextPresets.muted_sm), usuario=auth) \
            if permisos.puede(auth, "ver_marco_calidad") else _no_autorizado()
    if not _puede(auth, "ver_marco_calidad", m):
        return _no_autorizado()
    gestiona = _puede(auth, "gestionar_marco_calidad", m)
    claves = {a["clave"]: a for a in marco.atributos(m["id"])}
    atributo = atributo if atributo in claves else ""
    r = marco.resumen(m["id"])
    arbol = marco.arbol(m["id"], atributo or None)
    if _puede(auth, "ver_evidencias_calidad", m):
        conteo = evidencias.conteo_por_criterio(m["id"])
        for d in arbol:
            for c in d["criterios"]:
                c["evidencias"] = conteo.get(c["id"], 0)
    escala = marco.escala(m["id"])
    return pagina(
        "Marco de calidad",
        Div(Div(H2("Marco de calidad"),
                P(m["nombre"], " · versión ", m["version"], " · ", _vigencia(m),
                  f" · evidencia de los últimos {m['ventana_anios']} años", cls=TextPresets.muted_sm),
                P(m["descripcion"], cls="text-sm mt-2 max-w-3xl") if m["descripcion"] else ""),
            Div(descarga("XLSX", f"{BASE}/xlsx"),
                Button(UkIcon("pencil", height=14, width=14), "Datos del marco", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"{BASE}/{m['id']}/editar", hx_target=f"#{ID_MODAL}") if gestiona else "",
                Button(UkIcon("plus", height=14, width=14), "Dimensión", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"{BASE}/{m['id']}/dimensiones/nueva", hx_target=f"#{ID_MODAL}") if gestiona else "",
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(*[Card(Div(str(v), cls="text-2xl font-semibold"), Div(t, cls=TextPresets.muted_sm), cls="text-center")
              for v, t in ((r["dimensiones"], "dimensiones"), (r["criterios"], "criterios"),
                           (r["activos"], "indicadores activos"), (r["automaticos"], "automáticos"),
                           (r["manuales"], "manuales"))],
            cls="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6"),
        Card(Div(Div(H3("Escala de valoración", cls="text-base font-semibold"),
                     P("Para los juicios por criterio de la autoevaluación.", cls=TextPresets.muted_sm),
                     cls="flex-1"),
                 _acciones(gestiona, _boton("pencil", "Editar la escala", hx_get=f"{BASE}/{m['id']}/escala",
                                            hx_target=f"#{ID_MODAL}")), cls="flex gap-3 mb-2"),
             Ul(*[Li(Span(f"{n['valor']}. {n['nombre']}", cls="font-medium"),
                     f": {n['descripcion']}" if n["descripcion"] else "") for n in escala],
                cls="text-sm space-y-1"), cls="mb-6"),
        _filtro_atributos(m["id"], atributo),
        P(f"Indicadores con el atributo «{claves[atributo]['nombre']}»: {claves[atributo]['descripcion'] or ''}",
          cls="text-sm mb-4") if atributo else "",
        Div(*[_dimension(d, gestiona and not atributo, m["id"]) for d in arbol], cls="space-y-6")
        if arbol else P("No hay indicadores con ese atributo.", cls=TextPresets.muted_sm),
        usuario=auth)


@rt(f"{BASE}/xlsx")
def get(auth):
    m = marco.de_unidad(_unidad())
    if not _puede(auth, "ver_marco_calidad", m):
        return _no_autorizado()
    return _archivo(marco.a_xlsx(m["id"]), f"marco-de-calidad-{m['version']}.xlsx", XLSX)


# --- Datos del marco y escala -------------------------------------------------------------------------------

def _botones_modal():
    return Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
               Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2")


def form_marco(m, d, errores=()):
    def v(k):
        return d.get(k) if d.get(k) is not None else ""
    return modal(
        "Datos del marco",
        Form(mensaje_error(*errores),
             LabelInput("Nombre", id="nombre", value=v("nombre"), required=True),
             Div(LabelInput("Versión", id="version", value=v("version"), required=True),
                 LabelInput("Años de evidencia", id="ventana_anios", type="number", min=1, max=10,
                            value=v("ventana_anios")), cls="grid grid-cols-2 gap-4"),
             LabelTextArea("Descripción", id="descripcion", value=v("descripcion"), rows=3),
             Div(LabelInput("Vigente desde", id="vigente_desde", type="date", value=v("vigente_desde")),
                 LabelInput("Vigente hasta", id="vigente_hasta", type="date", value=v("vigente_hasta")),
                 cls="grid grid-cols-2 gap-4"),
             P("Mientras el Consejo de Carrera no lo apruebe, deje la vigencia en blanco: el marco es un borrador. "
               "«Años de evidencia» es la ventana que usan los informes por omisión.", cls=TextPresets.muted_sm),
             _botones_modal(), hx_put=f"{BASE}/{m['id']}", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


def _marco_gestionable(auth, mid):
    m = marco.obtener(mid)
    if m is None:
        return None, _no_encontrado()
    return m, (None if _puede(auth, "gestionar_marco_calidad", m) else _no_autorizado())


@rt(f"{BASE}/{{mid}}/editar")
def get(auth, mid: int):
    m, error = _marco_gestionable(auth, mid)
    return error or form_marco(m, m)


@rt(f"{BASE}/{{mid}}")
def put(auth, sess, mid: int, nombre: str = "", version: str = "", descripcion: str = "", vigente_desde: str = "",
        vigente_hasta: str = "", ventana_anios: str = ""):
    m, error = _marco_gestionable(auth, mid)
    if error:
        return error
    x, errores = marco.validar_marco(dict(nombre=nombre, version=version, descripcion=descripcion,
                                          vigente_desde=vigente_desde, vigente_hasta=vigente_hasta,
                                          ventana_anios=ventana_anios))
    if errores:
        return form_marco(m, x, errores)
    marco.guardar_marco(mid, x)
    auditar(auth["id"], "editar_marco_calidad", "marco_calidad", mid, f"{x['nombre']} ({x['version']})")
    add_toast(sess, "Datos del marco guardados.", "success")
    return Redirect(BASE)


def form_escala(m, texto, errores=()):
    return modal(
        "Escala de valoración",
        Form(mensaje_error(*errores),
             LabelTextArea("Niveles, del más bajo al más alto (uno por línea: «Nombre: descripción»)", id="niveles",
                           value=texto, rows=7),
             P("De 2 a 7 niveles. Si la autoevaluación ya registró juicios (etapa 5), cambiar la escala no los "
               "modifica.", cls=TextPresets.muted_sm),
             _botones_modal(), hx_put=f"{BASE}/{m['id']}/escala", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/{{mid}}/escala")
def get(auth, mid: int):
    m, error = _marco_gestionable(auth, mid)
    if error:
        return error
    texto = "\n".join(f"{n['nombre']}: {n['descripcion']}" if n["descripcion"] else n["nombre"]
                      for n in marco.escala(mid))
    return form_escala(m, texto)


@rt(f"{BASE}/{{mid}}/escala")
def put(auth, sess, mid: int, niveles: str = ""):
    m, error = _marco_gestionable(auth, mid)
    if error:
        return error
    lista, errores = marco.validar_escala(niveles)
    if errores:
        return form_escala(m, niveles, errores)
    marco.guardar_escala(mid, lista)
    auditar(auth["id"], "editar_escala_calidad", "marco_calidad", mid, " · ".join(n["nombre"] for n in lista))
    add_toast(sess, "Escala guardada.", "success")
    return Redirect(BASE)


# --- Dimensiones y criterios --------------------------------------------------------------------------------

def form_simple(titulo, d, url, metodo, errores=(), referencia=False):
    def v(k):
        return d.get(k) or ""
    return modal(
        titulo,
        Form(mensaje_error(*errores),
             Div(LabelInput("Código", id="codigo", value=v("codigo"), required=True, maxlength=marco.LARGO_CODIGO),
                 Div(LabelInput("Nombre", id="nombre", value=v("nombre"), required=True,
                                maxlength=marco.LARGO_NOMBRE), cls="col-span-3"),
                 cls="grid grid-cols-4 gap-4"),
             LabelTextArea("Descripción", id="descripcion", value=v("descripcion"), rows=3),
             LabelInput("Se alinea con (políticas o dimensiones institucionales)", id="referencia",
                        value=v("referencia")) if referencia else "",
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"))


def _dimension_gestionable(auth, did):
    d = marco.dimension(did)
    if d is None:
        return None, _no_encontrado()
    _, error = _marco_gestionable(auth, d["marco_id"])
    return d, error


@rt(f"{BASE}/{{mid}}/dimensiones/nueva")
def get(auth, mid: int):
    _, error = _marco_gestionable(auth, mid)
    return error or form_simple("Nueva dimensión", {}, f"{BASE}/{mid}/dimensiones", "post", referencia=True)


@rt(f"{BASE}/{{mid}}/dimensiones")
def post(auth, sess, mid: int, codigo: str = "", nombre: str = "", descripcion: str = "", referencia: str = ""):
    _, error = _marco_gestionable(auth, mid)
    if error:
        return error
    x, errores = marco.validar_dimension(dict(codigo=codigo, nombre=nombre, descripcion=descripcion,
                                              referencia=referencia), mid)
    if errores:
        return form_simple("Nueva dimensión", x, f"{BASE}/{mid}/dimensiones", "post", errores, referencia=True)
    did = marco.crear_dimension(mid, x)
    auditar(auth["id"], "crear_dimension_calidad", "dimension_calidad", did, f"{x['codigo']} {x['nombre']}")
    add_toast(sess, "Dimensión creada.", "success")
    return Redirect(f"{BASE}#dimension-{did}")


@rt(f"{BASE}/dimensiones/{{did}}/editar")
def get(auth, did: int):
    d, error = _dimension_gestionable(auth, did)
    return error or form_simple("Editar dimensión", d, f"{BASE}/dimensiones/{did}", "put", referencia=True)


@rt(f"{BASE}/dimensiones/{{did}}")
def put(auth, sess, did: int, codigo: str = "", nombre: str = "", descripcion: str = "", referencia: str = ""):
    d, error = _dimension_gestionable(auth, did)
    if error:
        return error
    x, errores = marco.validar_dimension(dict(codigo=codigo, nombre=nombre, descripcion=descripcion,
                                              referencia=referencia), d["marco_id"], did)
    if errores:
        return form_simple("Editar dimensión", x, f"{BASE}/dimensiones/{did}", "put", errores, referencia=True)
    marco.actualizar_dimension(did, x)
    auditar(auth["id"], "editar_dimension_calidad", "dimension_calidad", did, f"{x['codigo']} {x['nombre']}")
    add_toast(sess, "Dimensión guardada.", "success")
    return Redirect(f"{BASE}#dimension-{did}")


@rt(f"{BASE}/dimensiones/{{did}}")
def delete(auth, sess, did: int):
    d, error = _dimension_gestionable(auth, did)
    if error:
        return error
    if not marco.eliminar_dimension(did):
        add_toast(sess, "La dimensión tiene criterios o síntesis de una autoevaluación: no se puede eliminar.", "error")
        return Redirect(BASE)
    auditar(auth["id"], "eliminar_dimension_calidad", "dimension_calidad", did, f"{d['codigo']} {d['nombre']}")
    add_toast(sess, "Dimensión eliminada.", "success")
    return Redirect(BASE)


def _criterio_gestionable(auth, cid):
    c = marco.criterio(cid)
    if c is None:
        return None, _no_encontrado()
    _, error = _marco_gestionable(auth, c["marco_id"])
    return c, error


@rt(f"{BASE}/dimensiones/{{did}}/criterios/nuevo")
def get(auth, did: int):
    d, error = _dimension_gestionable(auth, did)
    return error or form_simple(f"Nuevo criterio de {d['codigo']}", {"codigo": f"{d['codigo']}."},
                                f"{BASE}/dimensiones/{did}/criterios", "post")


@rt(f"{BASE}/dimensiones/{{did}}/criterios")
def post(auth, sess, did: int, codigo: str = "", nombre: str = "", descripcion: str = ""):
    d, error = _dimension_gestionable(auth, did)
    if error:
        return error
    x, errores = marco.validar_criterio(dict(codigo=codigo, nombre=nombre, descripcion=descripcion), d["marco_id"])
    if errores:
        return form_simple(f"Nuevo criterio de {d['codigo']}", x, f"{BASE}/dimensiones/{did}/criterios", "post",
                           errores)
    cid = marco.crear_criterio(did, x)
    auditar(auth["id"], "crear_criterio_calidad", "criterio_calidad", cid, f"{x['codigo']} {x['nombre']}")
    add_toast(sess, "Criterio creado.", "success")
    return Redirect(f"{BASE}#criterio-{cid}")


@rt(f"{BASE}/criterios/{{cid}}/editar")
def get(auth, cid: int):
    c, error = _criterio_gestionable(auth, cid)
    return error or form_simple("Editar criterio", c, f"{BASE}/criterios/{cid}", "put")


@rt(f"{BASE}/criterios/{{cid}}")
def put(auth, sess, cid: int, codigo: str = "", nombre: str = "", descripcion: str = ""):
    c, error = _criterio_gestionable(auth, cid)
    if error:
        return error
    x, errores = marco.validar_criterio(dict(codigo=codigo, nombre=nombre, descripcion=descripcion), c["marco_id"], cid)
    if errores:
        return form_simple("Editar criterio", x, f"{BASE}/criterios/{cid}", "put", errores)
    marco.actualizar_criterio(cid, x)
    auditar(auth["id"], "editar_criterio_calidad", "criterio_calidad", cid, f"{x['codigo']} {x['nombre']}")
    add_toast(sess, "Criterio guardado.", "success")
    return Redirect(f"{BASE}#criterio-{cid}")


@rt(f"{BASE}/criterios/{{cid}}")
def delete(auth, sess, cid: int):
    c, error = _criterio_gestionable(auth, cid)
    if error:
        return error
    if not marco.eliminar_criterio(cid):
        add_toast(sess, "El criterio tiene indicadores, evidencias o juicios de una autoevaluación: no se puede eliminar (los indicadores se pueden desactivar).", "error")
        return Redirect(BASE)
    auditar(auth["id"], "eliminar_criterio_calidad", "criterio_calidad", cid, f"{c['codigo']} {c['nombre']}")
    add_toast(sess, "Criterio eliminado.", "success")
    return Redirect(f"{BASE}#dimension-{c['dimension_id']}")


# --- Indicadores --------------------------------------------------------------------------------------------

def _select(etiqueta, nombre, opciones, actual):
    return Div(FormLabel(etiqueta, fr=nombre),
               Select(*[Option(t, value=v, selected=v == actual) for v, t in opciones], id=nombre, name=nombre,
                      cls="uk-select"), cls="space-y-2")


def form_indicador(titulo, d, mid, url, metodo, errores=()):
    def v(k):
        return d.get(k) or ""
    fuentes = [("manual", "Manual (se registra a mano)")] + [
        (f"auto:{k}", f"Automática: {t}") for k, t in sorted(marco.FUENTES_AUTOMATICAS.items(), key=lambda x: x[1])]
    marcados = {int(a) for a in d.get("atributos") or []}
    return modal(
        titulo,
        Form(mensaje_error(*errores),
             Div(LabelInput("Código", id="codigo", value=v("codigo"), required=True, maxlength=marco.LARGO_CODIGO),
                 Div(LabelInput("Nombre", id="nombre", value=v("nombre"), required=True,
                                maxlength=marco.LARGO_NOMBRE), cls="col-span-3"), cls="grid grid-cols-4 gap-4"),
             Div(_select("Tipo", "tipo", [("", "—")] + list(marco.TIPOS.items()), v("tipo")),
                 _select("Frecuencia", "frecuencia", list(marco.FRECUENCIAS.items()), v("frecuencia") or "anual"),
                 _select("Lectura", "sentido", list(marco.SENTIDOS.items()), v("sentido") or "mayor"),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
             LabelTextArea("Fórmula (cómo se calcula, en palabras)", id="formula", value=v("formula"), rows=2),
             Div(Div(_select("Fuente", "fuente", fuentes, v("fuente") or "manual"), cls="col-span-2"),
                 LabelInput("Unidad", id="unidad_medida", value=v("unidad_medida"), placeholder="%, número, años…"),
                 cls="grid grid-cols-3 gap-4"),
             Div(LabelInput("Responsable", id="responsable", value=v("responsable")),
                 LabelInput("Referencia (política, objetivo o meta institucional)", id="referencia",
                            value=v("referencia")), cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             Div(FormLabel("Atributos (criterios de calidad de la UMSA de los que da evidencia)"),
                 Div(*[Label(CheckboxX(name="atributos", value=str(a["id"]), checked=a["id"] in marcados),
                             Span(a["nombre"], title=a["descripcion"] or ""), cls="flex items-center gap-2 text-sm")
                       for a in marco.atributos(mid)], cls="grid grid-cols-2 sm:grid-cols-4 gap-2"),
                 cls="space-y-2"),
             Label(CheckboxX(name="publico", value="1", checked=bool(d.get("publico"))),
                   Span("Publicar en la página pública de indicadores (solo años cerrados y cifras con base de al menos "
                        f"{publico.MIN_BASE})"), cls="flex items-center gap-2 text-sm"),
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-3xl")


async def _datos_indicador(req):
    f = await req.form()
    d = {k: f.get(k, "") for k in ("codigo", "nombre", "tipo", "formula", "fuente", "unidad_medida", "frecuencia",
                                   "sentido", "responsable", "referencia", "publico")}
    d["atributos"] = f.getlist("atributos")
    return d


@rt(f"{BASE}/criterios/{{cid}}/indicadores/nuevo")
def get(auth, cid: int):
    c, error = _criterio_gestionable(auth, cid)
    return error or form_indicador(f"Nuevo indicador de {c['codigo']}", {"codigo": f"{c['codigo']}."}, c["marco_id"],
                                   f"{BASE}/criterios/{cid}/indicadores", "post")


@rt(f"{BASE}/criterios/{{cid}}/indicadores")
async def post(auth, sess, req, cid: int):
    c, error = _criterio_gestionable(auth, cid)
    if error:
        return error
    x, errores = marco.validar_indicador(await _datos_indicador(req), c["marco_id"])
    if errores:
        return form_indicador(f"Nuevo indicador de {c['codigo']}", x, c["marco_id"],
                              f"{BASE}/criterios/{cid}/indicadores", "post", errores)
    iid = marco.crear_indicador(cid, x)
    auditar(auth["id"], "crear_indicador_calidad", "indicador_calidad", iid, f"{x['codigo']} {x['nombre']}")
    add_toast(sess, "Indicador creado.", "success")
    return Redirect(f"{BASE}/indicadores/{iid}")


def _indicador_visible(auth, iid, accion="ver_marco_calidad"):
    i = marco.indicador(iid)
    if i is None:
        return None, _no_encontrado()
    return i, (None if _puede(auth, accion, marco.obtener(i["marco_id"])) else _no_autorizado())


def _dato(titulo, *valor):
    return Div(Div(titulo, cls=TextPresets.muted_sm), Div(*valor, cls="text-sm"), cls="space-y-1")


def _metas(i, gestiona):
    url = f"{BASE}/indicadores/{i['id']}/metas"
    filas = [Tr(Td(str(mt["anio"])), Td(f"{mt['valor']:g}", " ", i["unidad_medida"] or ""), Td(mt["nota"] or ""),
                Td(_boton("trash-2", f"Quitar la meta de {mt['anio']}", hx_delete=f"{url}/{mt['anio']}",
                          hx_confirm=f"¿Quitar la meta de {mt['anio']}?") if gestiona else ""))
             for mt in i["metas"]]
    return Card(
        H3("Metas por año", cls="text-base font-semibold mb-2"),
        Table(Thead(Tr(Th("Año"), Th("Meta"), Th("Nota"), Th(""))), Tbody(*filas),
              cls="uk-table uk-table-divider uk-table-small text-sm") if filas else
        P("Sin metas registradas.", cls=TextPresets.muted_sm),
        Form(Div(LabelInput("Año", id="anio", type="number", min=2000, max=2100, required=True),
                 LabelInput("Meta", id="valor", inputmode="decimal", required=True),
                 Div(LabelInput("Nota (opcional)", id="nota"), cls="col-span-2"),
                 cls="grid grid-cols-2 sm:grid-cols-4 gap-4"),
             Div(Button("Guardar meta", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end"),
             hx_post=url, hx_target="body", cls="space-y-3 mt-4") if gestiona else "",
        P("Para un indicador «mejor si baja», la meta es el máximo aceptable; si no, el mínimo. Guardar otra meta "
          "para un año que ya tiene una la reemplaza.", cls=(TextPresets.muted_sm, "mt-2")) if gestiona else "",
        cls="mt-6")


def _serie(i, registra):
    """Cifras de la ventana de evidencia con su meta y semáforo; en los manuales, el registro de cifras."""
    m = marco.obtener(i["marco_id"])
    anios = indicadores.anios_de(m)
    celdas, cerrados = indicadores.serie(i, anios), indicadores.cierres(m["id"])
    manual = i["fuente"] == "manual"
    url = f"{BASE}/indicadores/{i['id']}/valores"
    filas = []
    for a in reversed(anios):
        x = celdas[a]
        quitar = (_boton("trash-2", f"Quitar la cifra de {a}", hx_delete=f"{url}/{a}", hx_target="body",
                         hx_confirm=f"¿Quitar la cifra de {a}?")
                  if registra and manual and x["origen"] == "manual" else "")
        filas.append(Tr(Td(str(a), " ", UkIcon("lock", height=12, width=12) if a in cerrados else ""),
                        Td(cifra(x, i["unidad_medida"], detalle=False)), Td(numero(x["n"]) if x["n"] is not None else "—"),
                        Td(numero(x["meta"])), Td(Div(x["detalle"] or "", cls="text-xs"),
                                                 Div(indicadores.ORIGENES.get(x["origen"], ""), cls=TextPresets.muted_sm)),
                        Td(quitar)))
    abiertos = [a for a in anios if a not in cerrados]
    return Card(
        H3("Cifras", cls="text-base font-semibold mb-2"),
        Div(Table(Thead(Tr(Th("Año", cls="w-20"), Th("Cifra", cls="w-28"), Th("Base (n)", cls="w-20"),
                           Th("Meta", cls="w-20"), Th("Cómo se obtuvo"), Th("", cls="w-12"))), Tbody(*filas),
                  cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[40rem]"),
            cls="overflow-x-auto"),
        Form(Div(Div(FormLabel("Año", fr="anio-cifra"),
                     Select(*[Option(str(a), value=str(a)) for a in reversed(abiertos)], id="anio-cifra", name="anio",
                            cls="uk-select")),
                 LabelInput("Cifra", id="valor-cifra", name="valor", inputmode="decimal", required=True),
                 LabelInput("Base (n, opcional)", id="n-cifra", name="n", inputmode="numeric"),
                 LabelInput("Fuente (acta, encuesta…)", id="fuente-cifra", name="fuente"),
                 Div(LabelInput("Nota (opcional)", id="nota-cifra", name="nota"), cls="sm:col-span-4"),
                 cls="grid grid-cols-2 sm:grid-cols-4 gap-4"),
             Div(Button("Guardar cifra", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end"),
             hx_post=url, hx_target="body", cls="space-y-3 mt-4") if registra and manual and abiertos else "",
        P("Indicador manual: sus cifras se registran a mano, una por año; guardar otra para el mismo año la reemplaza. "
          "Los años cerrados no se modifican." if manual else
          "El sistema calcula estas cifras con los datos registrados; la del año en curso es parcial.",
          cls=(TextPresets.muted_sm, "mt-2")),
        cls="mt-6")


@rt(f"{BASE}/indicadores/{{iid}}")
def get(auth, iid: int):
    i, error = _indicador_visible(auth, iid)
    if error:
        return error
    m = marco.obtener(i["marco_id"])
    gestiona = _puede(auth, "gestionar_marco_calidad", m)
    registra = _puede(auth, "registrar_indicadores_calidad", m)
    return pagina(
        f"Indicador {i['codigo']}",
        A(UkIcon("arrow-left", height=14, width=14), "Marco de calidad", href=f"{BASE}#criterio-{i['criterio_id']}",
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(Div(H2(Span(i["codigo"], cls="font-mono mr-2"), i["nombre"]),
                P(f"{i['dimension_codigo']} {i['dimension_nombre']} · {i['criterio_codigo']} {i['criterio_nombre']}",
                  cls=TextPresets.muted_sm),
                Div(insignia("Inactivo", "gris") if not i["activo"] else insignia("Activo", "verde"),
                    _insignia_fuente(i), cls="flex gap-2 mt-2")),
            _acciones(gestiona,
                      Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
                             hx_get=f"{BASE}/indicadores/{iid}/editar", hx_target=f"#{ID_MODAL}"),
                      Button("Desactivar" if i["activo"] else "Activar", cls=(ButtonT.ghost, ButtonT.sm),
                             hx_post=f"{BASE}/indicadores/{iid}/{'desactivar' if i['activo'] else 'activar'}",
                             hx_target="body"),
                      Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
                             hx_delete=f"{BASE}/indicadores/{iid}", hx_target="body",
                             hx_confirm=f"¿Eliminar el indicador {i['codigo']}?") if not i["metas"] else ""),
            cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(Div(_dato("Fórmula", i["formula"] or "—"),
                 _dato("Fuente", marco.fuente_texto(i["fuente"])),
                 Div(_dato("Tipo", marco.TIPOS[i["tipo"]]), _dato("Unidad", i["unidad_medida"] or "—"),
                     _dato("Frecuencia", marco.FRECUENCIAS[i["frecuencia"]]),
                     _dato("Lectura", marco.SENTIDOS[i["sentido"]]), cls="grid grid-cols-2 sm:grid-cols-4 gap-4"),
                 Div(_dato("Responsable", i["responsable"] or "—"), _dato("Referencia", i["referencia"] or "—"),
                     cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
                 _dato("Página pública", A("Se publica", href="/publico/indicadores", cls="text-primary hover:underline")
                       if i["publico"] else "No se publica"),
                 _dato("Atributos", Div(*[A(insignia(a["nombre"], "azul", titulo=a["descripcion"]),
                                            href=f"{BASE}?atributo={a['clave']}") for a in i["atributos"]],
                                        cls="flex flex-wrap gap-1") if i["atributos"] else "—"),
                 cls="space-y-4")),
        _serie(i, registra),
        _metas(i, gestiona),
        usuario=auth)


@rt(f"{BASE}/indicadores/{{iid}}/editar")
def get(auth, iid: int):
    i, error = _indicador_visible(auth, iid, "gestionar_marco_calidad")
    if error:
        return error
    return form_indicador(f"Editar {i['codigo']}", {**i, "atributos": [a["id"] for a in i["atributos"]]},
                          i["marco_id"], f"{BASE}/indicadores/{iid}", "put")


@rt(f"{BASE}/indicadores/{{iid}}")
async def put(auth, sess, req, iid: int):
    i, error = _indicador_visible(auth, iid, "gestionar_marco_calidad")
    if error:
        return error
    x, errores = marco.validar_indicador(await _datos_indicador(req), i["marco_id"], iid)
    if errores:
        return form_indicador(f"Editar {i['codigo']}", x, i["marco_id"], f"{BASE}/indicadores/{iid}", "put", errores)
    marco.actualizar_indicador(iid, x)
    auditar(auth["id"], "editar_indicador_calidad", "indicador_calidad", iid, f"{x['codigo']} {x['nombre']}")
    add_toast(sess, "Indicador guardado.", "success")
    return Redirect(f"{BASE}/indicadores/{iid}")


def _activar(auth, sess, iid, activo):
    i, error = _indicador_visible(auth, iid, "gestionar_marco_calidad")
    if error:
        return error
    marco.activar_indicador(iid, activo)
    auditar(auth["id"], "activar_indicador_calidad" if activo else "desactivar_indicador_calidad", "indicador_calidad",
            iid, i["codigo"])
    add_toast(sess, "Indicador activado." if activo else "Indicador desactivado: deja de calcularse y de pedirse.",
              "success")
    return Redirect(f"{BASE}/indicadores/{iid}")


@rt(f"{BASE}/indicadores/{{iid}}/activar")
def post(auth, sess, iid: int):
    return _activar(auth, sess, iid, True)


@rt(f"{BASE}/indicadores/{{iid}}/desactivar")
def post(auth, sess, iid: int):
    return _activar(auth, sess, iid, False)


@rt(f"{BASE}/indicadores/{{iid}}")
def delete(auth, sess, iid: int):
    i, error = _indicador_visible(auth, iid, "gestionar_marco_calidad")
    if error:
        return error
    if not marco.eliminar_indicador(iid):
        add_toast(sess, "El indicador tiene metas: desactívelo en lugar de eliminarlo.", "error")
        return Redirect(f"{BASE}/indicadores/{iid}")
    auditar(auth["id"], "eliminar_indicador_calidad", "indicador_calidad", iid, f"{i['codigo']} {i['nombre']}")
    add_toast(sess, "Indicador eliminado.", "success")
    return Redirect(f"{BASE}#criterio-{i['criterio_id']}")


@rt(f"{BASE}/indicadores/{{iid}}/metas")
def post(auth, sess, iid: int, anio: str = "", valor: str = "", nota: str = ""):
    i, error = _indicador_visible(auth, iid, "gestionar_marco_calidad")
    if error:
        return error
    x, errores = marco.validar_meta(anio, valor, nota)
    if errores:
        add_toast(sess, " ".join(errores), "error")
        return Redirect(f"{BASE}/indicadores/{iid}")
    marco.guardar_meta(iid, x)
    auditar(auth["id"], "meta_indicador_calidad", "indicador_calidad", iid, f"{i['codigo']} {x['anio']}: {x['valor']:g}")
    add_toast(sess, f"Meta de {x['anio']} guardada.", "success")
    return Redirect(f"{BASE}/indicadores/{iid}")


@rt(f"{BASE}/indicadores/{{iid}}/metas/{{anio}}")
def delete(auth, sess, iid: int, anio: int):
    i, error = _indicador_visible(auth, iid, "gestionar_marco_calidad")
    if error:
        return error
    marco.eliminar_meta(iid, anio)
    auditar(auth["id"], "quitar_meta_indicador_calidad", "indicador_calidad", iid, f"{i['codigo']} {anio}")
    add_toast(sess, f"Meta de {anio} quitada.", "success")
    return Redirect(f"{BASE}/indicadores/{iid}")


@rt(f"{BASE}/indicadores/{{iid}}/valores")
def post(auth, sess, iid: int, anio: str = "", valor: str = "", n: str = "", fuente: str = "", nota: str = ""):
    i, error = _indicador_visible(auth, iid, "registrar_indicadores_calidad")
    if error:
        return error
    x, errores = indicadores.validar_valor(anio, valor, n, fuente, nota)
    if i["fuente"] != "manual":
        errores.append("Las cifras de este indicador las calcula el sistema.")
    elif not errores and x["anio"] in indicadores.cierres(i["marco_id"]):
        errores.append(f"{x['anio']} está cerrado: reábralo en el tablero de indicadores para cambiar sus cifras.")
    if errores:
        add_toast(sess, " ".join(errores), "error")
        return Redirect(f"{BASE}/indicadores/{iid}")
    indicadores.registrar(iid, x, auth["id"])
    auditar(auth["id"], "cifra_indicador_calidad", "indicador_calidad", iid, f"{i['codigo']} {x['anio']}: {x['valor']:g}")
    add_toast(sess, f"Cifra de {x['anio']} guardada.", "success")
    return Redirect(f"{BASE}/indicadores/{iid}")


@rt(f"{BASE}/indicadores/{{iid}}/valores/{{anio}}")
def delete(auth, sess, iid: int, anio: int):
    i, error = _indicador_visible(auth, iid, "registrar_indicadores_calidad")
    if error:
        return error
    if anio in indicadores.cierres(i["marco_id"]):
        add_toast(sess, f"{anio} está cerrado: reábralo en el tablero de indicadores para cambiar sus cifras.", "error")
        return Redirect(f"{BASE}/indicadores/{iid}")
    indicadores.quitar(iid, anio)
    auditar(auth["id"], "quitar_cifra_indicador_calidad", "indicador_calidad", iid, f"{i['codigo']} {anio}")
    add_toast(sess, f"Cifra de {anio} quitada.", "success")
    return Redirect(f"{BASE}/indicadores/{iid}")
