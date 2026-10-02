"""Registro y edición de productos: formulario, importación por DOI o arXiv, revista y duplicados."""
import json
from datetime import date

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, HtmxResponseHeaders, Input, Label, Li, Option, P, Redirect,
                             Response, Select, Span, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import (Button, ButtonT, CheckboxX, Form, FormLabel, LabelInput, LabelTextArea, TextPresets,
                           UkIcon)

from app.investigacion import actividades, importacion, productos, proyectos, revistas
from app.comun import personas
from app.investigacion import filiacion as filiacion_mod
from app.investigacion.componentes import personas as selector_personas
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, boton_espera, mensaje_error, modal
from app.comun.componentes.registros import insignia
from app.investigacion.componentes.registros import casillas_proyectos
from app.comun.db import auditar
from app.investigacion.rutas.productos.lista import EVENTO

rt = APIRouter()


# --- Formulario -----------------------------------------------------------------------

# Cómo usar los campos generales en tipos que no son publicaciones.
AYUDA_TIPO = {
    "Patente": "Patente: en «Revista, editorial o medio» indique la oficina (p. ej., SENAPI) y en «Número» el número "
               "de solicitud o registro. Estado: «Enviado» = solicitada, «Publicado» = concedida.",
    "Tesis dirigida": "Tesis dirigida: en «Autores» ponga primero al tesista y luego a quienes la dirigen. Registre "
                      "al tesista como estudiante (Investigadores → Estudiantes y tesistas) para que cuente en los informes "
                      "de acreditación. Estado: «En preparación» = en curso; «Publicado» = defendida.",
    "Traducción": "Traducción: en el título, el título traducido; en «Resumen», la obra original y su autor. En "
                  "«Revista, editorial o medio», la editorial.",
}


def insignia_estado_revista(r):
    return insignia("verificada", "verde", icono="badge-check") if r["estado"] == "verificada" \
        else insignia("pendiente de verificar", "ambar", icono="clock")


RECARGAR = dict(hx_get="/productos/campos", hx_include="closest form", hx_target="#campos-dependientes",
                hx_swap="outerHTML")


def bloque_revista(revista_id, anio, nueva):
    """Artículos en revista: la revista del catálogo (o la propuesta de una nueva). Devuelve
    (bloque, clasificación según el catálogo o None)."""
    r = revistas.obtener(int(revista_id)) if str(revista_id or "").isdigit() else None
    if r:
        verificada = r["estado"] == "verificada"
        c = revistas.clasificacion(r["id"], int(anio)) if verificada and str(anio or "").isdigit() else None
        bloque = Div(
            FormLabel("Revista"),
            Div(Input(type="hidden", name="revista_id", value=str(r["id"])),
                Div(Span(r["titulo"], cls="font-medium"),
                    Span(" · " + " / ".join(x for x in (r["issn"], r["eissn"]) if x), cls="font-mono text-xs")
                    if r["issn"] or r["eissn"] else "", cls="min-w-0"),
                insignia("Verificada en el catálogo", "verde", icono="badge-check") if verificada
                else insignia("Pendiente de verificar", "ambar", icono="clock"),
                fh.Button("Cambiar", type="button", cls="text-sm text-primary hover:underline ml-auto",
                          hx_vals='{"revista_id": ""}', **RECARGAR),
                cls="flex flex-wrap items-center gap-2 rounded-md border border-border px-3 py-2"),
            P("La revista está verificada: el nivel de revisión y los índices se toman del catálogo según el año "
              "de publicación." if verificada else
              "La revista aún no está verificada por la administración: indique usted el nivel de revisión y los "
              "índices; cuando se verifique, se aplicará el catálogo.", cls=TextPresets.muted_sm),
            cls="space-y-2")
        return bloque, c
    buscador = Div(
        Input(type="search", name="revista_q", placeholder="Buscar revista del catálogo por título o ISSN…",
              autocomplete="off", cls="uk-input", aria_label="Buscar revista",
              hx_get="/productos/revistas", hx_trigger="input changed delay:250ms, search",
              hx_target="#resultados-revista", onkeydown="if(event.key==='Enter')event.preventDefault()"),
        Div(id="resultados-revista"), cls="relative")
    propuesta = fh.Details(
        fh.Summary("¿No está en el catálogo? Propóngala", cls="cursor-pointer text-sm text-primary"),
        Div(LabelInput("Título de la revista", id="revista_nueva_titulo", value=nueva.get("titulo") or ""),
            Div(LabelInput("ISSN", id="revista_nueva_issn", value=nueva.get("issn") or ""),
                LabelInput("ISSN electrónico", id="revista_nueva_eissn", value=nueva.get("eissn") or ""),
                cls="grid grid-cols-2 gap-3"),
            P("Se agregará al catálogo como pendiente; la administración la verificará.", cls=TextPresets.muted_sm),
            cls="space-y-2 mt-2"),
        open=bool(nueva.get("titulo")), cls="rounded-md border border-border p-3")
    return Div(FormLabel("Revista"), buscador, propuesta, cls="space-y-2"), None


def bloque_dependiente(uid, tipo_id, revision, indices_sel, actividad_id, revista_id=None, anio=None, nueva=None):
    """Campos que dependen del tipo: revista (en artículos), nivel de revisión, índices y actividad
    asociada."""
    t = productos.tipo(tipo_id) if str(tipo_id).isdigit() else None
    partes = []
    if t and t["nombre"] == revistas.TIPO_ARTICULO:
        bloque, c = bloque_revista(revista_id, anio, nueva or {})
        partes.append(bloque)
        if c:  # clasificación del catálogo: no se declara
            nombres = ", ".join(x["indice"] for x in c["indices"]) or "ningún índice"
            partes.append(Div(
                Input(type="hidden", name="revision", value=c["revision"]),
                *[Input(type="hidden", name="indice", value=str(x["indice_id"])) for x in c["indices"]],
                P(Span("Según el catálogo", cls="font-medium"), f", en {anio} la revista figuraba en {nombres}: ",
                  Span(productos.REVISIONES[c["revision"]].lower(), cls="font-medium"), ".", cls="text-sm"),
                cls="rounded-md bg-muted/50 p-3"))
            return Div(*partes, id="campos-dependientes", cls="space-y-4")
    if t and not t["admite_revision"]:
        partes.append(P(UkIcon("info", height=14, width=14, cls="inline mr-1"),
                        f"«{t['nombre']}» se registra como sin arbitraje y no cuenta como artículo para el "
                        "informe del instituto" + (" (se informa aparte, como resultado de I+D+i)."
                                                   if t["nombre"] in AYUDA_TIPO else "."),
                        cls=TextPresets.muted_sm))
        if t["nombre"] in AYUDA_TIPO:
            partes.append(P(AYUDA_TIPO[t["nombre"]], cls="text-sm"))
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
        casillas_proyectos("producto", pid, auth, proyectos_sel, preseleccion, d.get("_agradece")),
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
                paginas, doi, arxiv_id, url, resumen, actividad_id, mes="", revista_id=""):
    return dict(tipo_id=tipo_id, titulo=titulo, anio=anio, mes=mes, revista_id=revista_id,
                estado_publicacion=estado_publicacion,
                revision=revision, medio=medio, volumen=volumen, numero=numero, paginas=paginas,
                doi=doi, arxiv_id=arxiv_id, url=url, resumen=resumen, actividad_id=actividad_id)


def _autores_de_refs(refs, filiaciones=None):
    """Autores del formulario a partir de las listas paralelas `autor` y `filiacion`."""
    filiaciones = list(filiaciones or []) + [None] * len(refs or [])
    return [{**p, "filiacion": f} for p, f in ((personas.por_ref(r), f) for r, f in zip(refs or [], filiaciones)) if p]


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
    filiaciones = [info["resumen"]["filiacion"].get(ref) for ref in refs]
    if info["resumen"]["filiacion"]:
        info["avisos"].append("La filiación IIMAT/UMSA se marcó según la afiliación publicada: revísela.")
    return _modal_form(auth, d, _autores_de_refs(refs, filiaciones), [], proyectos_sel=proyecto or [],
                       importado=info)


@rt("/productos/campos")
def get(auth, tipo_id: str = "", revision: str = "", indice: list[str] = None,
        actividad_id: str = "", revista_id: str = "", anio: str = "", revista_nueva_titulo: str = "",
        revista_nueva_issn: str = "", revista_nueva_eissn: str = ""):
    return bloque_dependiente(auth["id"], tipo_id, revision, indice or [], actividad_id, revista_id, anio,
                              {"titulo": revista_nueva_titulo, "issn": revista_nueva_issn, "eissn": revista_nueva_eissn})


@rt("/productos/revistas")
def get(revista_q: str = ""):
    """Autocompletar de revistas del catálogo (título o ISSN)."""
    if len(revista_q.strip()) < 2:
        return ""
    encontradas = revistas.buscar(revista_q, limite=12)
    opciones = [Li(fh.Button(
        Span(r["titulo"], cls="font-medium"),
        Span(" · ".join(x for x in (r["issn"], r["eissn"], revistas.ESTADOS[r["estado"]].lower()) if x),
             cls=TextPresets.muted_sm),
        type="button", cls="w-full text-left flex flex-col px-3 py-2 hover:bg-muted",
        hx_vals=f'{{"revista_id": "{r["id"]}"}}', **RECARGAR)) for r in encontradas]
    if not opciones:
        opciones = [Li(P("No está en el catálogo: propóngala más abajo.", cls=(TextPresets.muted_sm, "px-3 py-2")))]
    return Ul(*opciones, cls="absolute z-30 w-full mt-1 max-h-72 overflow-y-auto rounded-md border border-border "
                            "bg-background shadow-lg divide-y divide-border")


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
        return _modal_form(auth, {**datos, **nueva, "_agradece": agradece}, _autores_de_refs(autor, filiacion),
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
         revista_nueva_issn: str = "", revista_nueva_eissn: str = ""):
    datos = _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                        paginas, doi, arxiv_id, url, resumen, actividad_id, mes, revista_id)
    nueva = dict(revista_nueva_titulo=revista_nueva_titulo, revista_nueva_issn=revista_nueva_issn,
                 revista_nueva_eissn=revista_nueva_eissn)
    return _guardar(auth, sess, None, datos, autor, indice, proyecto, filiacion, agradece, nueva)


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
        resumen: str = "", actividad_id: str = "", mes: str = "", autor: list[str] = None,
        indice: list[str] = None, proyecto: list[int] = None, filiacion: list[str] = None,
        agradece: list[str] = None, revista_id: str = "", revista_nueva_titulo: str = "",
        revista_nueva_issn: str = "", revista_nueva_eissn: str = ""):
    p = productos.obtener(pid)
    if not p or not productos.puede_editar(p, auth["id"]):
        return Response("No autorizado", status_code=403)
    datos = _datos_form(tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
                        paginas, doi, arxiv_id, url, resumen, actividad_id, mes, revista_id)
    nueva = dict(revista_nueva_titulo=revista_nueva_titulo, revista_nueva_issn=revista_nueva_issn,
                 revista_nueva_eissn=revista_nueva_eissn)
    return _guardar(auth, sess, pid, datos, autor, indice, proyecto, filiacion, agradece, nueva)


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
