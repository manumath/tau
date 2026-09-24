"""«Mis productos»: lista con filtros, alta/edición en modal, ficha con adjuntos.

Patrones HTMX:
- La lista escucha el evento `productos-cambiados`; tras guardar o eliminar, el servidor lo
  dispara con la cabecera HX-Trigger y la lista se recarga con los filtros vigentes.
- El bloque «revisión / índices / actividad» depende del tipo y del nivel de revisión elegidos:
  se vuelve a pedir al servidor cuando cambian (/productos/campos).
- Al escribir un DOI o arXiv se avisa si el producto ya existe (/productos/verificar).
"""
import json
from datetime import date

from fasthtml.common import (A, APIRouter, Div, H3, HtmxResponseHeaders, Input, Label, Option, P,
                             Redirect, Response, Select, Span)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, CheckboxX, Form, FormLabel, LabelInput,
                           LabelTextArea, TextPresets, UkIcon)

from app import actividades, importacion, personas, productos, proyectos
from app.components import personas as selector_personas
from app.components.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.components.registros import (casillas_proyectos, dato, enlace_persona, filtros, insignia,
                                      insignias_proyectos, seccion_adjuntos, url_filtrada)
from app.db import auditar

rt = APIRouter()

EVENTO = "productos-cambiados"
ID_LISTA = "lista-productos"
ID_FILTROS = "filtros-productos"


# --- Presentación --------------------------------------------------------------------

def insignias(p):
    res = [insignia(p["tipo"])]
    if p["revision"] == "indexado":
        nombres = ", ".join(i["nombre"] for i in p["indices"])
        res.append(insignia("Indexado", "azul", titulo=nombres))
    elif p["revision"] == "arbitrado":
        res.append(insignia("Arbitrado", "azul"))
    if p["estado_publicacion"] != "publicado":
        res.append(insignia(productos.ESTADOS[p["estado_publicacion"]], "ambar"))
    if productos.cuenta_para_informe(p):
        res.append(insignia("Cuenta para el informe", "verde", icono="check"))
    return Div(*res, cls="flex flex-wrap gap-1.5")


def autores_texto(p):
    partes = []
    for i, a in enumerate(p["autores"]):
        if i:
            partes.append(", ")
        partes.append(enlace_persona(a, "font-medium" if a["interno"] else ""))
    return Span(*partes, cls="text-sm")


def item(p, uid):
    medio = " · ".join(str(x) for x in (p["medio"], p["volumen"] and f"vol. {p['volumen']}",
                                        p["paginas"] and f"pp. {p['paginas']}") if x)
    acciones = Div(
        Button(UkIcon("pencil", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon),
               title="Editar", aria_label=f"Editar {p['titulo']}",
               hx_get=f"/productos/{p['id']}/editar", hx_target=f"#{ID_MODAL}")
        if productos.puede_editar(p, uid) else "",
        Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon),
               title="Eliminar", aria_label=f"Eliminar {p['titulo']}",
               hx_delete=f"/productos/{p['id']}",
               hx_confirm=_confirmacion_eliminar(p))
        if productos.puede_eliminar(p, uid) else "",
        cls="flex shrink-0")
    return Div(
        Div(str(p["anio"]), cls="font-mono text-sm text-muted-foreground w-12 shrink-0 pt-0.5"),
        Div(A(p["titulo"], href=f"/productos/{p['id']}", cls="block font-medium hover:underline"),
            Div(autores_texto(p)),
            P(medio, cls=TextPresets.muted_sm) if medio else "",
            insignias(p),
            Div(*insignias_proyectos(proyectos.vinculos_de("producto", p["id"])),
                cls="flex flex-wrap gap-1.5"),
            cls="min-w-0 flex-1 space-y-1"),
        acciones,
        cls="flex gap-4 py-4")


def _confirmacion_eliminar(p):
    otros = [a for a in p["autores"] if a["interno"]]
    aviso = " También desaparecerá del perfil de sus coautores del instituto." if len(otros) > 1 else ""
    return f"¿Eliminar «{p['titulo']}»?{aviso}"


def lista(uid, q="", anio="", tipo="", informe=False):
    items = productos.de_investigador(uid, q, anio, tipo, informe)
    n_informe = sum(productos.cuenta_para_informe(p) for p in items)
    contenido = (
        [P(f"{len(items)} producto{'s' if len(items) != 1 else ''} · {n_informe} cuenta"
           f"{'n' if n_informe != 1 else ''} para el informe del instituto",
           cls=TextPresets.muted_sm),
         Div(*[item(p, uid) for p in items], cls="divide-y divide-border")]
        if items else [P("No hay productos que coincidan." if (q or anio or tipo or informe)
                         else "Aún no registra productos. Use «Nuevo producto» para empezar.",
                         cls=(TextPresets.muted_sm, "py-8 text-center"))])
    return Div(*contenido, id=ID_LISTA, hx_get="/productos/lista", hx_include=f"#{ID_FILTROS}",
               hx_trigger=f"{EVENTO} from:body", hx_swap="outerHTML")


# --- Formulario -----------------------------------------------------------------------

def bloque_dependiente(uid, tipo_id, revision, indices_sel, actividad_id):
    """Campos que dependen del tipo: nivel de revisión, índices y actividad asociada."""
    t = productos.tipo(tipo_id) if str(tipo_id).isdigit() else None
    partes = []
    if t and not t["admite_revision"]:
        partes.append(P(UkIcon("info", height=14, width=14, cls="inline mr-1"),
                        f"«{t['nombre']}» se registra como sin arbitraje y no cuenta para el "
                        "informe del instituto.", cls=TextPresets.muted_sm))
    else:
        radios = [Label(Input(type="radio", name="revision", value=v, checked=v == revision,
                              cls="uk-radio", hx_get="/productos/campos",
                              hx_include="closest form", hx_target="#campos-dependientes",
                              hx_swap="outerHTML"),
                        Span(texto), cls="flex items-center gap-2")
                  for v, texto in productos.REVISIONES.items()]
        partes.append(Div(FormLabel("Nivel de revisión"), Div(*radios, cls="flex flex-wrap gap-4"),
                          cls="space-y-2"))
        if revision == "indexado":
            casillas = [Label(CheckboxX(name="indice", value=str(i["id"]),
                                        checked=str(i["id"]) in indices_sel),
                              Span(i["nombre"]),
                              Span("(no cuenta como indexado)", cls=TextPresets.muted_sm)
                              if not i["cuenta_como_indexado"] else "",
                              cls="flex items-center gap-2")
                        for i in productos.indices()]
            partes.append(Div(FormLabel("Índices en que figura"),
                              Div(*casillas, cls="grid grid-cols-1 sm:grid-cols-2 gap-2"),
                              cls="space-y-2"))
    if t and t["nombre"] == productos.TIPO_PRESENTACION:
        opciones = actividades.para_selector(uid)
        if actividad_id and str(actividad_id).isdigit() and \
                all(str(a["id"]) != str(actividad_id) for a in opciones):
            if (a := actividades.obtener(int(actividad_id))):
                opciones.insert(0, a)
        partes.append(Div(
            FormLabel("Presentada en la actividad", fr="actividad_id"),
            Select(Option("— Ninguna —", value=""),
                   *[Option(f"{a['titulo']} ({actividades.fechas_texto(a)})", value=str(a["id"]),
                            selected=str(a["id"]) == str(actividad_id or "")) for a in opciones],
                   id="actividad_id", name="actividad_id", cls="uk-select"),
            P("Registre primero la actividad en «Mis actividades» si no aparece.",
              cls=TextPresets.muted_sm),
            cls="space-y-2"))
    return Div(*partes, id="campos-dependientes", cls="space-y-4")


def caja_importar(valor="", error=None, contenido=None):
    """Recuadro «Importar desde DOI o arXiv» (solo al crear). `contenido` reemplaza al mensaje
    de ayuda, p. ej. con el aviso de que el producto ya existe."""
    return Div(
        Div(UkIcon("download", height=16, width=16, cls="shrink-0 text-primary"),
            Span("Importar desde DOI o arXiv", cls="font-medium text-sm"), cls="flex items-center gap-2"),
        Div(Input(id="identificador", name="identificador", value=valor, autocomplete="off",
                  placeholder="10.1090/S0002-9947-1965-0170805-7  ·  2401.01234  ·  o la URL",
                  cls="uk-input", aria_label="DOI o identificador arXiv",
                  onkeydown="if(event.key==='Enter'){event.preventDefault();"
                            "document.getElementById('boton-importar').click()}"),
            Button("Importar", type="button", id="boton-importar",
                   cls=(ButtonT.primary, "shrink-0"), hx_post="/productos/importar",
                   hx_include="#identificador, input[name=proyecto]:checked", hx_target=f"#{ID_MODAL}",
                   hx_indicator="#importando", hx_disabled_elt="this"),
            cls="flex gap-2"),
        Span(UkIcon("loader-circle", height=14, width=14, cls="animate-spin"),
             " Consultando Crossref / arXiv…", id="importando", cls="htmx-indicator text-sm"),
        mensaje_error(error) if error else "",
        contenido or P("Completa el formulario con los datos publicados: título, autores (reconoce a "
                       "los del instituto), revista, año, páginas y resumen. Luego puede revisarlos.",
                       cls=TextPresets.muted_sm),
        id="caja-importar", cls="rounded-md border border-dashed border-primary/40 bg-primary/5 p-3 space-y-2")


def banner_importacion(info):
    """Resumen de lo importado: fuente, autores reconocidos y avisos."""
    r = info["resumen"]
    lineas = []
    if r["internos"]:
        lineas.append(f"Del instituto: {', '.join(r['internos'])}.")
    if r["existentes"]:
        lineas.append(f"Externos ya registrados: {', '.join(r['existentes'])}.")
    if r["nuevos"]:
        lineas.append(f"Externos nuevos (se registrarán al guardar): {', '.join(r['nuevos'])}.")
    avisos = [Div(UkIcon("triangle-alert", height=14, width=14, cls="shrink-0 mt-0.5"), Span(a),
                  cls="flex gap-1.5 text-sm text-amber-700 dark:text-amber-400") for a in info["avisos"]]
    version = Button(UkIcon("download", height=14, width=14), f"Importar versión publicada ({info['doi_publicado']})",
                     type="button", cls=(ButtonT.default, ButtonT.sm), hx_post="/productos/importar",
                     hx_vals=json.dumps({"identificador": info["doi_publicado"],
                                         "arxiv_asociado": info["arxiv_id"]}),
                     hx_include="input[name=proyecto]:checked", hx_target=f"#{ID_MODAL}") \
        if info.get("doi_publicado") else ""
    return Div(
        Div(UkIcon("circle-check", height=16, width=16, cls="shrink-0 text-green-600"),
            Span(f"Datos importados de {info['fuente']}. Revíselos antes de guardar."),
            cls="flex items-center gap-1.5 font-medium text-sm"),
        *[P(x, cls="text-sm") for x in lineas], *avisos, version,
        cls="rounded-md border border-green-300 bg-green-50 dark:bg-green-950/40 dark:border-green-800 "
            "p-3 space-y-1")


def form_producto(auth, d, autores_elegidos, indices_sel, errores=(), pid=None, proyectos_sel=None,
                  preseleccion=None, importado=None):
    uid = auth["id"]
    def campo(etiqueta, nombre, **kw):
        return LabelInput(etiqueta, id=nombre, value=d.get(nombre) or "", **kw)

    return Form(
        banner_importacion(importado) if importado else ("" if pid else caja_importar()),
        mensaje_error(*errores),
        Input(type="hidden", name="pid", value=pid or ""),
        Div(Div(FormLabel("Tipo", fr="tipo_id"),
                Select(*[Option(t["nombre"], value=str(t["id"]),
                                selected=str(t["id"]) == str(d.get("tipo_id")))
                         for t in productos.tipos()],
                       id="tipo_id", name="tipo_id", cls="uk-select",
                       hx_get="/productos/campos", hx_include="closest form",
                       hx_target="#campos-dependientes", hx_swap="outerHTML"),
                cls="space-y-2 sm:col-span-2"),
            campo("Año", "anio", type="number", min=1900, max=date.today().year + 1, required=True),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
        campo("Título", "titulo", required=True),
        selector_personas.selector("autor", autores_elegidos, "Autores",
                                   "En el orden de la publicación. Use las flechas para reordenar."),
        Div(Div(FormLabel("Estado", fr="estado_publicacion"),
                Select(*[Option(t, value=v, selected=v == d.get("estado_publicacion"))
                         for v, t in productos.ESTADOS.items()],
                       id="estado_publicacion", name="estado_publicacion", cls="uk-select"),
                cls="space-y-2"),
            campo("Revista, editorial o medio", "medio"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        bloque_dependiente(uid, d.get("tipo_id"), d.get("revision"), indices_sel,
                           d.get("actividad_id")),
        Div(campo("Volumen", "volumen"), campo("Número", "numero"), campo("Páginas", "paginas"),
            cls="grid grid-cols-3 gap-4"),
        Div(campo("DOI", "doi", placeholder="10.1234/abcd", hx_post="/productos/verificar",
                  hx_trigger="change", hx_target="#aviso-duplicado"),
            campo("arXiv", "arxiv_id", placeholder="2401.01234", hx_post="/productos/verificar",
                  hx_trigger="change", hx_target="#aviso-duplicado"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        Div(id="aviso-duplicado"),
        campo("Enlace (URL)", "url", type="url", placeholder="https://…"),
        LabelTextArea("Resumen", id="resumen", value=d.get("resumen") or "", rows=4,
                      placeholder="Admite LaTeX: $\\zeta(s)$"),
        casillas_proyectos("producto", pid, auth, proyectos_sel, preseleccion),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
            Button("Guardar", type="submit", cls=ButtonT.primary),
            cls="flex justify-end gap-2"),
        hx_put=f"/productos/{pid}" if pid else None, hx_post=None if pid else "/productos",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


def _modal_form(auth, d, autores_elegidos, indices_sel, errores=(), pid=None, proyectos_sel=None,
                preseleccion=None, importado=None):
    return modal("Editar producto" if pid else "Nuevo producto",
                 form_producto(auth, d, autores_elegidos, indices_sel, errores, pid, proyectos_sel,
                               preseleccion, importado),
                 ancho="max-w-3xl")


def _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                paginas, doi, arxiv_id, url, resumen, actividad_id):
    return dict(tipo_id=tipo_id, titulo=titulo, anio=anio, estado_publicacion=estado_publicacion,
                revision=revision, medio=medio, volumen=volumen, numero=numero, paginas=paginas,
                doi=doi, arxiv_id=arxiv_id, url=url, resumen=resumen, actividad_id=actividad_id)


def _autores_de_refs(refs):
    return [p for p in (personas.por_ref(r) for r in refs or []) if p]


# --- Rutas: lista ---------------------------------------------------------------------

@rt("/productos")
def get(auth, q: str = "", anio: str = "", tipo: str = "", informe: bool = False):
    uid = auth["id"]
    casilla_informe = Label(CheckboxX(name="informe", value="1", checked=informe),
                            Span("Solo los que cuentan para el informe"),
                            cls="flex items-center gap-2 text-sm")
    return pagina(
        "Mis productos",
        Div(Div(H2("Mis productos"),
                P("Artículos, libros, reportes, presentaciones y más. Un producto con varios autores "
                  "del instituto se registra una sola vez y aparece en el perfil de cada uno.",
                  cls=TextPresets.muted_sm)),
            Div(A(UkIcon("download", height=16, width=16), "Exportar BibTeX", href="/productos/bibtex",
                  # Exporta lo que se ve: agrega los filtros vigentes (están en la URL de la página).
                  onclick="this.href='/productos/bibtex'+location.search",
                  cls="uk-btn uk-btn-default inline-flex items-center gap-1"),
                Button(UkIcon("file-up", height=16, width=16), "Importar BibTeX", cls=ButtonT.default,
                       hx_get="/productos/importar-bibtex", hx_target=f"#{ID_MODAL}"),
                Button(UkIcon("plus", height=16, width=16), "Nuevo producto", cls=ButtonT.primary,
                       hx_get="/productos/nuevo", hx_target=f"#{ID_MODAL}"),
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        filtros(ID_FILTROS, "/productos/lista", ID_LISTA, q, anio, productos.anios_de(uid), tipo,
                productos.tipos(), extra=[casilla_informe]),
        Card(lista(uid, q, anio, tipo, informe)),
        usuario=auth, seccion="productos")


@rt("/productos/lista")
def get(auth, q: str = "", anio: str = "", tipo: str = "", informe: bool = False):
    return (lista(auth["id"], q, anio, tipo, informe),
            HtmxResponseHeaders(replace_url=url_filtrada("/productos", q=q, anio=anio, tipo=tipo,
                                                         informe="1" if informe else "")))


# --- Rutas: formulario -------------------------------------------------------------------

@rt("/productos/nuevo")
def get(auth, proyecto: int = None):
    tipo_articulo = next((t for t in productos.tipos() if t["nombre"] == "Artículo en revista"),
                         productos.tipos()[0])
    d = dict(tipo_id=tipo_articulo["id"], anio=date.today().year, estado_publicacion="publicado",
             revision="arbitrado")
    return _modal_form(auth, d, _autores_de_refs([f"i:{auth['id']}"]), [], preseleccion=proyecto)


@rt("/productos/importar")
def post(auth, identificador: str = "", arxiv_asociado: str = "", proyecto: list[int] = None):
    """Consulta Crossref o arXiv y devuelve el formulario completo, prellenado.
    Si hay un error o el producto ya existe, solo se actualiza el recuadro de importación."""
    def en_la_caja(*args, **kw):
        return caja_importar(*args, **kw), HtmxResponseHeaders(retarget="#caja-importar", reswap="outerHTML")

    try:
        info = importacion.importar(identificador, arxiv_asociado or None)
    except importacion.ErrorImportacion as e:
        return en_la_caja(identificador, str(e))
    d = info["datos"]
    if (otro := productos.existente(d["doi"], d["arxiv_id"])):
        return en_la_caja(identificador, contenido=aviso_duplicado(otro, auth["id"]))
    refs, info["resumen"] = importacion.resolver_autores(info["autores"])
    if f"i:{auth['id']}" not in refs:
        info["avisos"].append("Usted no aparece entre los autores reconocidos. Si es coautor(a), "
                              "agréguese o revise que su nombre coincida con el publicado.")
    info["arxiv_id"] = d["arxiv_id"]
    return _modal_form(auth, d, _autores_de_refs(refs), [], proyectos_sel=proyecto or [], importado=info)


@rt("/productos/campos")
def get(auth, tipo_id: str = "", revision: str = "", indice: list[str] = None,
        actividad_id: str = ""):
    return bloque_dependiente(auth["id"], tipo_id, revision, indice or [], actividad_id)


@rt("/productos/verificar")
def post(auth, doi: str = "", arxiv_id: str = "", pid: str = ""):
    try:
        doi_n = productos.normalizar_doi(doi) if doi.strip() else None
        arxiv_n = productos.normalizar_arxiv(arxiv_id) if arxiv_id.strip() else None
    except ValueError as e:
        return P(str(e), cls="text-sm text-amber-600")
    otro = productos.existente(doi_n, arxiv_n, excluir=int(pid) if pid.isdigit() else None)
    return aviso_duplicado(otro, auth["id"]) if otro else ""


def aviso_duplicado(otro, uid):
    ya_es_autor = productos.es_autor(otro["id"], uid)
    return Div(
        Div(UkIcon("copy", height=16, width=16, cls="shrink-0"),
            Div(P("Este producto ya está registrado:", cls="font-medium"),
                P(productos.cita(otro), cls="text-sm")),
            cls="flex gap-2"),
        Div(A("Ver ficha", href=f"/productos/{otro['id']}", target="_blank",
              cls="text-sm text-primary hover:underline"),
            Span("Usted ya figura como autor.", cls="text-sm") if ya_es_autor else
            Button("Sumarme como autor", type="button", cls=(ButtonT.primary, ButtonT.sm),
                   hx_post=f"/productos/{otro['id']}/sumarme", hx_target=f"#{ID_MODAL}"),
            cls="flex items-center gap-4 mt-2"),
        cls="rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/40 "
            "dark:border-amber-800 p-3")


def _guardar(auth, sess, pid, datos, autor, indice, proyecto):
    d, errores = productos.preparar(datos, autor or [], indice or [], pid)
    if errores:
        return _modal_form(auth, datos, _autores_de_refs(autor), indice or [], errores, pid,
                           proyecto or [])
    nuevo = pid is None
    autor = [personas.materializar(r, auth["id"]) for r in autor]  # externos importados
    pid = productos.guardar(d, autor, auth["id"], pid)
    for aviso in proyectos.sincronizar("producto", pid, proyecto or [], auth):
        add_toast(sess, aviso, "warning")
    auditar(auth["id"], "crear_producto" if nuevo else "editar_producto", "producto", pid)
    add_toast(sess, "Producto registrado." if nuevo else "Cambios guardados.", "success")
    # Vacía el modal y avisa a la lista (o ficha) y al contador de pendientes que se recarguen.
    return "", HtmxResponseHeaders(trigger=f"{EVENTO}, pendientes-cambiados")


@rt("/productos")
def post(auth, sess, tipo_id: str = "", titulo: str = "", anio: str = "",
         estado_publicacion: str = "", revision: str = "", medio: str = "", volumen: str = "",
         numero: str = "", paginas: str = "", doi: str = "", arxiv_id: str = "", url: str = "",
         resumen: str = "", actividad_id: str = "", autor: list[str] = None,
         indice: list[str] = None, proyecto: list[int] = None):
    datos = _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                        paginas, doi, arxiv_id, url, resumen, actividad_id)
    return _guardar(auth, sess, None, datos, autor, indice, proyecto)


@rt("/productos/{pid}/editar")
def get(auth, pid: int):
    p = productos.obtener(pid)
    if not p or not productos.puede_editar(p, auth["id"]):
        return Response("No autorizado", status_code=403)
    return _modal_form(auth, p, p["autores"], [str(i["id"]) for i in p["indices"]], pid=pid)


@rt("/productos/{pid}")
def put(auth, sess, pid: int, tipo_id: str = "", titulo: str = "", anio: str = "",
        estado_publicacion: str = "", revision: str = "", medio: str = "", volumen: str = "",
        numero: str = "", paginas: str = "", doi: str = "", arxiv_id: str = "", url: str = "",
        resumen: str = "", actividad_id: str = "", autor: list[str] = None,
        indice: list[str] = None, proyecto: list[int] = None):
    p = productos.obtener(pid)
    if not p or not productos.puede_editar(p, auth["id"]):
        return Response("No autorizado", status_code=403)
    datos = _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                        paginas, doi, arxiv_id, url, resumen, actividad_id)
    return _guardar(auth, sess, pid, datos, autor, indice, proyecto)


@rt("/productos/{pid}/sumarme")
def post(auth, sess, pid: int):
    p = productos.obtener(pid)
    if not p:
        return Response(status_code=404)
    productos.sumar_autor(pid, auth["id"])
    auditar(auth["id"], "sumarse_autor", "producto", pid)
    add_toast(sess, f"Ahora figura como autor(a) de «{p['titulo']}».", "success")
    return "", HtmxResponseHeaders(trigger=EVENTO)


@rt("/productos/{pid}")
def delete(auth, sess, pid: int, desde: str = ""):
    p = productos.obtener(pid)
    if not p or not productos.puede_eliminar(p, auth["id"]):
        return Response("No autorizado", status_code=403)
    productos.eliminar(pid)
    auditar(auth["id"], "eliminar_producto", "producto", pid, p["titulo"])
    add_toast(sess, "Producto eliminado.", "success")
    if desde == "ficha":
        return Redirect("/productos")
    return "", HtmxResponseHeaders(trigger=EVENTO)


# --- Ficha -------------------------------------------------------------------------------

def ficha(p, auth):
    uid = auth["id"]
    editable = productos.puede_editar(p, uid)
    actividad = actividades.obtener(p["actividad_id"]) if p["actividad_id"] else None
    enlaces = [A(f"doi:{p['doi']}", href=f"https://doi.org/{p['doi']}", target="_blank",
                 rel="noopener", cls="text-primary hover:underline") if p["doi"] else "",
               A(f"arXiv:{p['arxiv_id']}", href=f"https://arxiv.org/abs/{p['arxiv_id']}",
                 target="_blank", rel="noopener", cls="text-primary hover:underline")
               if p["arxiv_id"] else "",
               A("Enlace", href=p["url"], target="_blank", rel="noopener noreferrer",
                 cls="text-primary hover:underline") if p["url"] else ""]
    acciones = Div(
        Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
               hx_get=f"/productos/{p['id']}/editar", hx_target=f"#{ID_MODAL}") if editable else "",
        Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
               hx_delete=f"/productos/{p['id']}?desde=ficha", hx_confirm=_confirmacion_eliminar(p))
        if productos.puede_eliminar(p, uid) else "",
        cls="flex gap-2")
    return Div(
        Div(Div(insignias(p), H2(p["titulo"], cls="mt-2"), cls="min-w-0"), acciones,
            cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(
            dato("Autores", Div(*[Div(enlace_persona(a), Span(f" · {a['afiliacion']}",
                                                             cls=TextPresets.muted_sm)
                                      if a.get("afiliacion") else "") for a in p["autores"]])),
            dato("Año", str(p["anio"])),
            dato("Estado", productos.ESTADOS[p["estado_publicacion"]]),
            dato("Medio", ", ".join(x for x in (p["medio"], p["volumen"] and f"vol. {p['volumen']}",
                                                p["numero"] and f"n.º {p['numero']}",
                                                p["paginas"] and f"pp. {p['paginas']}") if x)),
            dato("Nivel de revisión", productos.REVISIONES[p["revision"]]
                 + (f" ({', '.join(i['nombre'] for i in p['indices'])})" if p["indices"] else "")),
            dato("Presentada en", A(actividad["titulo"], href=f"/actividades/{actividad['id']}",
                                    cls="text-primary hover:underline") if actividad else None),
            dato("Identificadores", Div(*[e for e in enlaces if e], cls="flex gap-4 flex-wrap"))
            if any(enlaces) else "",
            dato("Proyectos", Div(*insignias_proyectos(proyectos.vinculos_de("producto", p["id"])),
                                  cls="flex flex-wrap gap-1.5")
                 if proyectos.vinculos_de("producto", p["id"]) else None),
            dato("Cita", P(productos.cita(p), cls="text-sm")),
        ),
        Card(H3("Resumen", cls="text-base font-semibold mb-2"),
             P(p["resumen"], cls="whitespace-pre-line leading-relaxed")) if p["resumen"] else "",
        Card(H3("Archivos adjuntos", cls="text-base font-semibold mb-2"),
             seccion_adjuntos("producto", p["id"], editable)) if editable or auth["es_admin"] else "",
        id="ficha-producto", hx_get=f"/productos/{p['id']}/ficha", hx_select="#ficha-producto",
        hx_trigger=f"{EVENTO} from:body", hx_swap="outerHTML", cls="space-y-6")


@rt("/productos/{pid}/ficha")
def get(auth, pid: int):
    p = productos.obtener(pid)
    return ficha(p, auth) if p else Redirect("/productos")


@rt("/productos/{pid}")
def get(auth, pid: int):
    p = productos.obtener(pid)
    if not p:
        return Redirect("/productos")
    return pagina(p["titulo"],
                  A(UkIcon("arrow-left", height=14, width=14), "Mis productos", href="/productos",
                    cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  ficha(p, auth), usuario=auth, seccion="productos")
