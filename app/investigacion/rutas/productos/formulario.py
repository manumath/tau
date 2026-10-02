"""Alta y edición de productos: el formulario (con su recuadro de importación) y las rutas que lo
guardan o eliminan. Los campos que dependen del tipo están en `campos`; la importación por DOI o
arXiv y los avisos de duplicado, en `importar`."""
import json
from datetime import date

from fasthtml.common import APIRouter, Div, HtmxResponseHeaders, Input, Option, P, Redirect, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Form, FormLabel, LabelInput, LabelTextArea, TextPresets, UkIcon

from app.investigacion import msc, productos, proyectos, revistas
from app.comun import personas
from app.investigacion import filiacion as filiacion_mod
from app.investigacion.componentes import msc as msc_ui
from app.investigacion.componentes import personas as selector_personas
from app.comun.componentes.layout import ID_MODAL, boton_espera, mensaje_error, modal
from app.investigacion.componentes.registros import casillas_proyectos
from app.comun.db import auditar
from app.investigacion.rutas.productos.campos import RECARGAR, bloque_dependiente
from app.investigacion.rutas.productos.lista import EVENTO

rt = APIRouter()


def caja_importar(valor="", error=None, contenido=None):
    """Recuadro «Importar desde DOI o arXiv» (solo al crear). `contenido` reemplaza al mensaje
    de ayuda, p. ej. con el aviso de que el producto ya existe."""
    return Div(
        Div(UkIcon("download", height=16, width=16, cls="shrink-0 text-primary"),
            Span("Importar desde DOI o arXiv", cls="font-medium text-sm"), cls="flex items-center gap-2"),
        Div(Input(id="identificador", name="identificador", value=valor, autocomplete="off",
                  placeholder="10.1090/S0002-9947-1965-0170805-7  ·  2401.01234  ·  o la URL",
                  cls="uk-input", aria_label="DOI o identificador arXiv",
                  data_enter="clic:boton-importar"),
            boton_espera("Importar", type="button", id="boton-importar",
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
            campo("Año", "anio", type="number", min=1900, max=date.today().year + 1, required=True,
                  hx_trigger="change", **RECARGAR),  # el año cambia la clasificación según el catálogo
            Div(FormLabel("Mes (opcional)", fr="mes"),
                Select(Option("—", value=""),
                       *[Option(t.capitalize(), value=str(i), selected=str(i) == str(d.get("mes") or ""))
                         for i, t in enumerate(productos.MESES, start=1)],
                       id="mes", name="mes", cls="uk-select",
                       title="Permite ubicar el producto en informes por periodo (octubre a septiembre)."),
                cls="space-y-2"),
            cls="grid grid-cols-2 sm:grid-cols-4 gap-4"),
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
                           d.get("actividad_id"), d.get("revista_id"), d.get("anio"),
                           {k: d.get(f"revista_nueva_{k}") for k in ("titulo", "issn", "eissn")}),
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
        msc_ui.selector(msc_elegidos(d.get("msc")), d.get("_msc_origen", "")),
        casillas_proyectos("producto", pid, auth, proyectos_sel, preseleccion, d.get("_agradece")),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
            Button("Guardar", type="submit", cls=ButtonT.primary),
            cls="flex justify-end gap-2"),
        hx_put=f"/productos/{pid}" if pid else None, hx_post=None if pid else "/productos",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


def modal_form(auth, d, autores_elegidos, indices_sel, errores=(), pid=None, proyectos_sel=None,
                preseleccion=None, importado=None):
    return modal("Editar producto" if pid else "Nuevo producto",
                 form_producto(auth, d, autores_elegidos, indices_sel, errores, pid, proyectos_sel,
                               preseleccion, importado),
                 ancho="max-w-3xl")


def _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                paginas, doi, arxiv_id, url, resumen, actividad_id, mes="", revista_id="", codigos_msc=None):
    return dict(tipo_id=tipo_id, titulo=titulo, anio=anio, mes=mes, revista_id=revista_id,
                estado_publicacion=estado_publicacion,
                revision=revision, medio=medio, volumen=volumen, numero=numero, paginas=paginas,
                doi=doi, arxiv_id=arxiv_id, url=url, resumen=resumen, actividad_id=actividad_id,
                msc=codigos_msc or [])


def msc_elegidos(valor) -> list[dict]:
    """Clasificación para el selector: códigos ('11M06', del formulario o de una sugerencia) o filas
    del catálogo (de un producto guardado)."""
    return [m for m in ((msc.por_codigo(x) if isinstance(x, str) else x) for x in valor or []) if m]


def autores_de_refs(refs, filiaciones=None):
    """Autores del formulario a partir de las listas paralelas `autor` y `filiacion`."""
    filiaciones = list(filiaciones or []) + [None] * len(refs or [])
    return [{**p, "filiacion": f} for p, f in ((personas.por_ref(r), f) for r, f in zip(refs or [], filiaciones)) if p]



# --- Rutas ------------------------------------------------------------------------------

@rt("/productos/nuevo")
def get(auth, proyecto: int = None):
    tipo_articulo = next((t for t in productos.tipos() if t["nombre"] == "Artículo en revista"),
                         productos.tipos()[0])
    d = dict(tipo_id=tipo_articulo["id"], anio=date.today().year, estado_publicacion="publicado",
             revision="arbitrado", msc=msc.sugeridos_por_perfil([auth["id"]]), _msc_origen="su perfil")
    return modal_form(auth, d, autores_de_refs([f"i:{auth['id']}"]), [], preseleccion=proyecto)



def _revista_propuesta(d, nueva, uid) -> str | None:
    """Si el artículo no tiene revista del catálogo pero se propuso una, la busca por ISSN o título
    y, si no existe, la agrega al catálogo como pendiente. → error o None."""
    t = productos.tipo(d.get("tipo_id"))
    if d.get("revista_id") or not (nueva.get("revista_nueva_titulo") or "").strip() or \
            not t or t["nombre"] != revistas.TIPO_ARTICULO:
        return None
    datos, errores = revistas.validar({"titulo": nueva["revista_nueva_titulo"], "issn": nueva.get("revista_nueva_issn"),
                                       "eissn": nueva.get("revista_nueva_eissn")})
    existente = revistas.coincidir([datos.get("issn"), datos.get("eissn")], datos.get("titulo"))
    if existente:
        d["revista_id"], d["medio"] = existente["id"], existente["titulo"]
        return None
    if errores:
        return "Revista propuesta: " + " ".join(errores)
    rid = revistas.crear(datos, uid)
    auditar(uid, "proponer_revista", "revista", rid, datos["titulo"])
    d["revista_id"], d["medio"] = rid, datos["titulo"]
    return None


def _guardar(auth, sess, pid, datos, autor, indice, proyecto, filiacion=None, agradece=None, nueva=None):
    agradece = filiacion_mod.leer_agradece(agradece)
    nueva = nueva or {}
    d, errores = productos.preparar(datos, autor or [], indice or [], pid)
    if not errores and (error := _revista_propuesta(d, nueva, auth["id"])):
        errores = [error]
    if errores:
        return modal_form(auth, {**datos, **nueva, "_agradece": agradece}, autores_de_refs(autor, filiacion),
                           indice or [], errores, pid, proyecto or [])
    nuevo = pid is None
    autor = [personas.materializar(r, auth["id"]) for r in autor]  # externos importados
    pid = productos.guardar(d, autor, auth["id"], pid, filiacion)
    for aviso in proyectos.sincronizar("producto", pid, proyecto or [], auth):
        add_toast(sess, aviso, "warning")
    # Agradecimiento: en los proyectos en que queda vinculado (o propuesto).
    for v in proyectos.vinculos_de("producto", pid):
        if v["proyecto_id"] in agradece:
            proyectos.marcar_agradece(pid, v["proyecto_id"], agradece[v["proyecto_id"]])
    auditar(auth["id"], "crear_producto" if nuevo else "editar_producto", "producto", pid)
    add_toast(sess, "Producto registrado." if nuevo else "Cambios guardados.", "success")
    # Vacía el modal y avisa a la lista (o ficha) y al contador de pendientes que se recarguen.
    return "", HtmxResponseHeaders(trigger=f"{EVENTO}, pendientes-cambiados")


@rt("/productos")
def post(auth, sess, tipo_id: str = "", titulo: str = "", anio: str = "",
         estado_publicacion: str = "", revision: str = "", medio: str = "", volumen: str = "",
         numero: str = "", paginas: str = "", doi: str = "", arxiv_id: str = "", url: str = "",
         resumen: str = "", actividad_id: str = "", mes: str = "", autor: list[str] = None,
         indice: list[str] = None, proyecto: list[int] = None, filiacion: list[str] = None,
         agradece: list[str] = None, revista_id: str = "", revista_nueva_titulo: str = "",
         revista_nueva_issn: str = "", revista_nueva_eissn: str = "", msc: list[str] = None):
    datos = _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                        paginas, doi, arxiv_id, url, resumen, actividad_id, mes, revista_id, msc)
    nueva = dict(revista_nueva_titulo=revista_nueva_titulo, revista_nueva_issn=revista_nueva_issn,
                 revista_nueva_eissn=revista_nueva_eissn)
    return _guardar(auth, sess, None, datos, autor, indice, proyecto, filiacion, agradece, nueva)


@rt("/productos/{pid}/editar")
def get(auth, pid: int):
    p = productos.obtener(pid)
    if not p or not productos.puede_editar(p, auth["id"]):
        return Response("No autorizado", status_code=403)
    return modal_form(auth, p, p["autores"], [str(i["id"]) for i in p["indices"]], pid=pid)


@rt("/productos/{pid}")
def put(auth, sess, pid: int, tipo_id: str = "", titulo: str = "", anio: str = "",
        estado_publicacion: str = "", revision: str = "", medio: str = "", volumen: str = "",
        numero: str = "", paginas: str = "", doi: str = "", arxiv_id: str = "", url: str = "",
        resumen: str = "", actividad_id: str = "", mes: str = "", autor: list[str] = None,
        indice: list[str] = None, proyecto: list[int] = None, filiacion: list[str] = None,
        agradece: list[str] = None, revista_id: str = "", revista_nueva_titulo: str = "",
        revista_nueva_issn: str = "", revista_nueva_eissn: str = "", msc: list[str] = None):
    p = productos.obtener(pid)
    if not p or not productos.puede_editar(p, auth["id"]):
        return Response("No autorizado", status_code=403)
    datos = _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                        paginas, doi, arxiv_id, url, resumen, actividad_id, mes, revista_id, msc)
    nueva = dict(revista_nueva_titulo=revista_nueva_titulo, revista_nueva_issn=revista_nueva_issn,
                 revista_nueva_eissn=revista_nueva_eissn)
    return _guardar(auth, sess, pid, datos, autor, indice, proyecto, filiacion, agradece, nueva)



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
