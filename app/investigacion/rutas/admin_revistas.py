"""Catálogo de revistas (administración): lista, ficha con indexaciones por año, verificación y
carga por CSV. Todo /admin/* exige ser administrador (Beforeware)."""
import base64

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Code, Div, HtmxResponseHeaders, Option, P, Redirect, Response, Select,
                             Span, Thead, Tr, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, H3, Button, ButtonT, Card, Form, FormLabel, Input, LabelInput, Table, Tbody, Td, Th,
                           TextPresets, UkIcon)

from app.comun import config
from app.investigacion import importar_revistas, revistas
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia, url_filtrada
from app.comun.db import auditar

rt = APIRouter()
BASE = "/admin/revistas"
ID_LISTA = "lista-revistas"


def insignia_estado(r):
    return insignia("Verificada", "verde", icono="badge-check") if r["estado"] == "verificada" \
        else insignia("Pendiente de verificar", "ambar", icono="clock")


def _si_no(v):
    return {1: "Sí", 0: "No"}.get(v, "—")


# --- Lista -------------------------------------------------------------------------------------------

def lista(q="", estado=""):
    filas = [Tr(Td(A(r["titulo"], href=f"{BASE}/{r['id']}", cls="font-medium hover:underline"),
                   Div(" · ".join(x for x in (r["editorial"], r["pais"]) if x), cls=TextPresets.muted_sm)),
                Td(Div(r["issn"] or "—", cls="font-mono text-sm"),
                   Div(f"e: {r['eissn']}", cls="font-mono text-xs text-muted-foreground") if r["eissn"] else "",
                   cls="whitespace-nowrap"),
                Td(", ".join(sorted({x["indice"] for x in revistas.indexaciones(r["id"]) if x["hasta"] is None})) or "—",
                   cls="text-sm"),
                Td(str(r["n_productos"]), cls="text-right text-sm"),
                Td(insignia_estado(r)))
             for r in revistas.buscar(q, estado)]
    return Div(Table(Thead(Tr(Th("Revista"), Th("ISSN"), Th("Índices vigentes"), Th("Productos", cls="text-right"),
                              Th("Estado"))),
                     Tbody(*filas) if filas else Tbody(Tr(Td("No hay revistas que coincidan.", colspan=5,
                                                             cls=(TextPresets.muted_sm, "text-center py-6")))),
                     cls="uk-table-divider uk-table-middle uk-table-hover"),
               id=ID_LISTA, cls="overflow-x-auto")


@rt(BASE)
def get(auth, q: str = "", estado: str = ""):
    estado = estado if estado in revistas.ESTADOS else ""
    return pagina(
        "Catálogo de revistas",
        Div(Div(H2("Catálogo de revistas"),
                P("Revistas donde publica el instituto y los índices en que figuran cada año, con la fuente "
                  "consultada. Una revista verificada define el nivel de revisión y los índices de los "
                  "artículos publicados en ella.", cls=TextPresets.muted_sm)),
            Div(A(UkIcon("link", height=16, width=16), f"Artículos sin revista ({sum(g['n'] for g in revistas.sin_vincular())})",
                  href=f"{BASE}/sin-vincular", cls="uk-btn uk-btn-default inline-flex items-center gap-1"),
                Button(UkIcon("file-up", height=16, width=16), "Importar CSV", cls=ButtonT.default,
                       hx_get=f"{BASE}/importar", hx_target=f"#{ID_MODAL}"),
                Button(UkIcon("plus", height=16, width=16), "Nueva revista", cls=ButtonT.primary,
                       hx_get=f"{BASE}/nueva", hx_target=f"#{ID_MODAL}"),
                cls="flex gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        fh.Form(Input(type="search", name="q", value=q, placeholder="Buscar por título o ISSN…", cls="max-w-sm",
                      aria_label="Buscar revistas"),
                Select(Option("Todas", value=""), *[Option(t, value=v, selected=v == estado)
                                                     for v, t in revistas.ESTADOS.items()],
                       name="estado", cls="uk-select w-56", aria_label="Estado"),
                hx_get=f"{BASE}/lista", hx_target=f"#{ID_LISTA}", hx_swap="outerHTML",
                hx_trigger="input delay:300ms, change, search", onsubmit="return false",
                cls="flex flex-wrap gap-3 mb-4"),
        Card(lista(q, estado)),
        usuario=auth, seccion="revistas")


@rt(f"{BASE}/lista")
def get(q: str = "", estado: str = ""):
    estado = estado if estado in revistas.ESTADOS else ""
    return lista(q, estado), HtmxResponseHeaders(replace_url=url_filtrada(BASE, q=q, estado=estado))


# --- Artículos sin revista del catálogo -----------------------------------------------------------------------

@rt(f"{BASE}/sin-vincular")
def get(auth):
    grupos = revistas.sin_vincular()
    todas = revistas.buscar(limite=2000)
    tarjetas = []
    for g in grupos:
        sugerida = g["sugerida"]
        tarjetas.append(Card(
            Div(Div(H3(g["medio"] or "(sin revista declarada)", cls="text-base font-semibold"),
                    P(f"{g['n']} artículo(s): " + "; ".join(f"{p['titulo']} ({p['anio']})" for p in g["productos"][:3])
                      + ("…" if g["n"] > 3 else ""), cls=TextPresets.muted_sm), cls="min-w-0"),
                cls="mb-3"),
            Form(Input(type="hidden", name="clave", value=g["clave"]),
                 Select(Option("— Elija la revista del catálogo —", value=""),
                        *[Option(f"{r['titulo']}" + (f" ({r['issn'] or r['eissn']})" if r["issn"] or r["eissn"] else ""),
                                 value=str(r["id"]), selected=bool(sugerida and sugerida["id"] == r["id"]))
                          for r in todas], name="revista_id", cls="uk-select max-w-md", aria_label="Revista"),
                 Button("Vincular", type="submit", name="accion", value="vincular", cls=(ButtonT.primary, ButtonT.sm)),
                 Button("Crear revista con este nombre", type="submit", name="accion", value="crear",
                        cls=(ButtonT.ghost, ButtonT.sm)) if g["medio"] else "",
                 hx_post=f"{BASE}/sin-vincular", cls="flex flex-wrap items-center gap-2")))
    return pagina(
        "Artículos sin revista",
        A(UkIcon("arrow-left", height=14, width=14), "Catálogo de revistas", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Artículos sin revista del catálogo"),
        P("Artículos en revista registrados sin elegir una revista del catálogo, agrupados por el nombre que "
          "declararon sus autores. Vincúlelos a una revista existente o cree la revista (quedará pendiente de "
          "verificar). Al vincular, el artículo toma el nombre de la revista y, si está verificada, su "
          "clasificación según el año.", cls=(TextPresets.muted_sm, "mb-6")),
        Div(*tarjetas, cls="space-y-4") if tarjetas else P("Todos los artículos tienen revista del catálogo.",
                                                          cls="text-sm text-green-700"),
        usuario=auth, seccion="revistas")


@rt(f"{BASE}/sin-vincular")
def post(auth, sess, clave: str = "", revista_id: str = "", accion: str = "vincular"):
    grupo = next((g for g in revistas.sin_vincular() if g["clave"] == clave), None)
    if not grupo:
        add_toast(sess, "Ese grupo ya no tiene artículos sin revista.", "warning")
        return Redirect(f"{BASE}/sin-vincular")
    if accion == "crear":
        existente = revistas.coincidir([], grupo["medio"])
        rid = existente["id"] if existente else revistas.crear({"titulo": grupo["medio"].strip()}, auth["id"])
    elif revista_id.isdigit() and revistas.obtener(int(revista_id)):
        rid = int(revista_id)
    else:
        add_toast(sess, "Elija la revista del catálogo.", "error")
        return Redirect(f"{BASE}/sin-vincular")
    n = revistas.vincular([p["id"] for p in grupo["productos"]], rid)
    auditar(auth["id"], "vincular_revista", "revista", rid, f"{n} artículo(s) de «{grupo['medio']}»")
    add_toast(sess, f"{n} artículo(s) vinculado(s) a «{revistas.obtener(rid)['titulo']}».", "success")
    return Redirect(f"{BASE}/sin-vincular")


# --- Alta y edición --------------------------------------------------------------------------------------

def _campos(d):
    def sel(nombre, etiqueta):
        actual = "" if d.get(nombre) is None else str(d.get(nombre))
        return Div(FormLabel(etiqueta, fr=nombre),
                   Select(*[Option(t, value=v, selected=v == actual) for v, t in (("", "Sin dato"), ("1", "Sí"), ("0", "No"))],
                          id=nombre, name=nombre, cls="uk-select"), cls="space-y-2")
    return (LabelInput("Título", id="titulo", value=d.get("titulo") or "", required=True),
            Div(LabelInput("ISSN (impreso)", id="issn", value=d.get("issn") or "", placeholder="1234-5679"),
                LabelInput("ISSN electrónico", id="eissn", value=d.get("eissn") or ""),
                LabelInput("País", id="pais", value=d.get("pais") or "", placeholder=config.PAIS),
                cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
            Div(LabelInput("Editorial", id="editorial", value=d.get("editorial") or ""),
                LabelInput("Sitio web", id="url", value=d.get("url") or "", placeholder="https://…"),
                cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
            Div(sel("arbitrada", "Revisión por pares"), sel("acceso_abierto", "Acceso abierto"),
                cls="grid grid-cols-2 gap-4"),
            LabelInput("Nota", id="nota", value=d.get("nota") or ""))


def _form(d, errores=(), rid=None):
    return Form(mensaje_error(*errores), *_campos(d),
                Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                    Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
                **({"hx_put": f"{BASE}/{rid}"} if rid else {"hx_post": BASE}), hx_target=f"#{ID_MODAL}",
                cls="space-y-4")


@rt(f"{BASE}/nueva")
def get():
    return modal("Nueva revista", _form({"pais": config.PAIS}), ancho="max-w-2xl")


def _datos_form(titulo, issn, eissn, pais, editorial, url, arbitrada, acceso_abierto, nota):
    return dict(titulo=titulo, issn=issn, eissn=eissn, pais=pais, editorial=editorial, url=url,
                arbitrada=arbitrada, acceso_abierto=acceso_abierto, nota=nota)


@rt(BASE)
def post(auth, sess, titulo: str = "", issn: str = "", eissn: str = "", pais: str = "", editorial: str = "",
         url: str = "", arbitrada: str = "", acceso_abierto: str = "", nota: str = ""):
    crudo = _datos_form(titulo, issn, eissn, pais, editorial, url, arbitrada, acceso_abierto, nota)
    d, errores = revistas.validar(crudo)
    if errores:
        return modal("Nueva revista", _form(crudo, errores), ancho="max-w-2xl")
    rid = revistas.crear(d, auth["id"], verificada=False)
    auditar(auth["id"], "crear_revista", "revista", rid, d["titulo"])
    add_toast(sess, "Revista creada. Agregue sus indexaciones y verifíquela.", "success")
    return Redirect(f"{BASE}/{rid}")


@rt(BASE + "/{rid}/editar")
def get(rid: int):
    r = revistas.obtener(rid)
    return modal("Editar revista", _form(r, rid=rid), ancho="max-w-2xl") if r else Response(status_code=404)


@rt(BASE + "/{rid}")
def put(auth, sess, rid: int, titulo: str = "", issn: str = "", eissn: str = "", pais: str = "",
        editorial: str = "", url: str = "", arbitrada: str = "", acceso_abierto: str = "", nota: str = ""):
    if not revistas.obtener(rid):
        return Response(status_code=404)
    crudo = _datos_form(titulo, issn, eissn, pais, editorial, url, arbitrada, acceso_abierto, nota)
    d, errores = revistas.validar(crudo, rid)
    if errores:
        return modal("Editar revista", _form(crudo, errores, rid), ancho="max-w-2xl")
    revistas.actualizar(rid, d)
    revistas.reclasificar(rid)  # «revisión por pares» cambia la clasificación de sus artículos
    auditar(auth["id"], "editar_revista", "revista", rid, d["titulo"])
    add_toast(sess, "Revista guardada.", "success")
    return Redirect(f"{BASE}/{rid}")


@rt(BASE + "/{rid}")
def delete(auth, sess, rid: int):
    r = revistas.obtener(rid)
    if not r:
        return Response(status_code=404)
    error = revistas.eliminar(rid)
    if error:
        add_toast(sess, error, "error")
        return Redirect(f"{BASE}/{rid}")
    auditar(auth["id"], "eliminar_revista", "revista", rid, r["titulo"])
    add_toast(sess, "Revista eliminada.", "success")
    return Redirect(BASE)


@rt(BASE + "/{rid}/verificar")
def post(auth, sess, rid: int, verificada: str = "1"):
    r = revistas.obtener(rid)
    if not r:
        return Response(status_code=404)
    revistas.verificar(rid, auth["id"], verificada == "1")
    n = revistas.reclasificar(rid)
    auditar(auth["id"], "verificar_revista" if verificada == "1" else "desverificar_revista", "revista", rid, r["titulo"])
    add_toast(sess, f"Revista verificada: se reclasificaron {n} artículo(s) según el catálogo." if verificada == "1"
              else "La revista volvió a «pendiente».", "success")
    return Redirect(f"{BASE}/{rid}")


# --- Ficha e indexaciones ---------------------------------------------------------------------------------

def tarjeta_indexaciones(r, errores=(), datos=None):
    rid = r["id"]
    datos = datos or {}
    filas = [Tr(Td(x["indice"], Span(" (no cuenta como indexado)", cls=TextPresets.muted_sm)
                   if not x["cuenta_como_indexado"] else ""),
                Td(f"{x['desde']}–{x['hasta'] or 'hoy'}"),
                Td(x["cuartil"] or "—"),
                Td(Div(x["fuente"] or "—", cls="text-sm"),
                   A("evidencia", href=x["evidencia_url"], target="_blank", rel="noopener",
                     cls="text-xs text-primary hover:underline") if x["evidencia_url"] else "",
                   Div(f"verificó {x['verificador'] or '—'} · {x['verificado_en'][:10]}", cls="text-xs text-muted-foreground")),
                Td(fh.Button(UkIcon("trash-2", height=14, width=14), type="button", aria_label="Quitar",
                             cls="p-1 rounded hover:bg-muted hover:text-red-600",
                             hx_delete=f"{BASE}/{rid}/indexacion/{x['id']}", hx_target="#indexaciones",
                             hx_swap="outerHTML", hx_confirm="¿Quitar esta indexación?")))
             for x in revistas.indexaciones(rid)]
    indices = revistas.indices_catalogo()
    agregar = Form(
        mensaje_error(*errores),
        Div(Div(FormLabel("Índice"), Select(Option("— Elija —", value=""),
                                          *[Option(i["nombre"], value=str(i["id"]),
                                                   selected=str(i["id"]) == str(datos.get("indice_id") or ""))
                                            for i in indices], name="indice_id", cls="uk-select"), cls="space-y-1"),
            LabelInput("Desde (año)", id="desde", type="number", min=1900, max=2100, value=datos.get("desde") or ""),
            LabelInput("Hasta (vacío = vigente)", id="hasta", type="number", min=1900, max=2100,
                       value=datos.get("hasta") or ""),
            Div(FormLabel("Cuartil"), Select(Option("—", value=""), *[Option(c, selected=c == datos.get("cuartil"))
                                                                     for c in revistas.CUARTILES],
                                             name="cuartil", cls="uk-select"), cls="space-y-1"),
            cls="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end"),
        Div(LabelInput("Fuente consultada", id="fuente", value=datos.get("fuente") or "",
                       placeholder="Lista maestra de Scopus, junio 2026"),
            LabelInput("Enlace de evidencia", id="evidencia_url", value=datos.get("evidencia_url") or "",
                       placeholder="https://…"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        Div(Button("Agregar indexación", type="submit", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"),
        hx_post=f"{BASE}/{rid}/indexacion", hx_target="#indexaciones", hx_swap="outerHTML", cls="space-y-3 mt-4")
    return Card(H3("Indexación por año", cls="text-base font-semibold mb-1"),
                P("En qué índices figura la revista y desde/hasta qué año, con la fuente consultada. Un artículo "
                  "cuenta como indexado si la revista figuraba en un índice que cuenta el año de su publicación.",
                  cls=(TextPresets.muted_sm, "mb-3")),
                Div(Table(Thead(Tr(Th("Índice"), Th("Años"), Th("Cuartil"), Th("Fuente y evidencia"), Th(""))),
                          Tbody(*filas) if filas else Tbody(Tr(Td("Sin indexaciones registradas.", colspan=5,
                                                                  cls=TextPresets.muted_sm))),
                          cls="uk-table-divider uk-table-small"), cls="overflow-x-auto"),
                agregar, id="indexaciones")


@rt(BASE + "/{rid}/indexacion")
def post(auth, rid: int, indice_id: str = "", desde: str = "", hasta: str = "", cuartil: str = "",
         fuente: str = "", evidencia_url: str = ""):
    r = revistas.obtener(rid)
    if not r:
        return Response(status_code=404)
    datos = dict(indice_id=indice_id, desde=desde, hasta=hasta, cuartil=cuartil, fuente=fuente,
                 evidencia_url=evidencia_url)
    errores = revistas.agregar_indexacion(rid, datos, auth["id"])
    if not errores:
        revistas.reclasificar(rid)
        auditar(auth["id"], "agregar_indexacion", "revista", rid, f"índice {indice_id} desde {desde}")
    return tarjeta_indexaciones(r, errores, datos if errores else None)


@rt(BASE + "/{rid}/indexacion/{iid}")
def delete(auth, rid: int, iid: int):
    r = revistas.obtener(rid)
    if not r:
        return Response(status_code=404)
    revistas.quitar_indexacion(rid, iid)
    revistas.reclasificar(rid)
    auditar(auth["id"], "quitar_indexacion", "revista", rid, str(iid))
    return tarjeta_indexaciones(r)


# --- Carga por CSV ------------------------------------------------------------------------------------------

def _form_archivo(errores=()):
    return Form(
        mensaje_error(*errores),
        P("Una fila por revista e índice: ", Code("titulo"), ", ", Code("issn"), " o ", Code("eissn"), " y, si quiere, ",
          Code("pais"), ", ", Code("editorial"), ", ", Code("arbitrada"), ", ", Code("acceso_abierto"), " (sí/no), ",
          Code("indice"), ", ", Code("desde"), ", ", Code("hasta"), ", ", Code("cuartil"), ", ", Code("fuente"), " y ",
          Code("evidencia"), ".", cls="text-sm"),
        P("Cargue solo las revistas donde publica el instituto. Las existentes se completan (no se borra nada) y "
          "lo cargado queda verificado.", cls=TextPresets.muted_sm),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{BASE}/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
            Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        hx_post=f"{BASE}/importar/revisar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}",
        cls="space-y-4")


@rt(f"{BASE}/importar")
def get():
    return modal("Importar revistas", _form_archivo(), ancho="max-w-2xl")


@rt(f"{BASE}/plantilla")
def get():
    return Response(importar_revistas.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-revistas.csv"'})


@rt(f"{BASE}/importar/revisar")
async def post(archivo: UploadFile = None):
    if archivo is None or not archivo.filename:
        return modal("Importar revistas", _form_archivo(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar_revistas.MAX_BYTES + 1)
    grupos, errores = importar_revistas.leer(contenido)
    if not grupos:
        return modal("Importar revistas", _form_archivo(errores), ancho="max-w-2xl")
    listas = [g for g in grupos if not g["errores"]]
    filas = [Tr(Td(Div(g["datos"]["titulo"] or "—", cls="font-medium"),
                   Div(g["datos"].get("issn") or g["datos"].get("eissn") or "sin ISSN", cls="font-mono text-xs")),
                Td("; ".join(f"{x['indice']} {x['desde']}–{x['hasta'] or 'hoy'}" for x in g["indexaciones"]) or "—",
                   cls="text-sm"),
                Td(Div(*[P(e, cls="text-sm text-red-600") for e in g["errores"]]) if g["errores"] else
                   Span("Se completa la existente" if g["existente"] else "Nueva", cls="text-sm")))
             for g in grupos]
    return modal(
        "Vista previa de revistas",
        P(f"{len(listas)} revista(s) se cargarán · {len(grupos) - len(listas)} con errores, se omiten.",
          cls="text-sm font-medium mb-3"),
        Div(Table(Thead(Tr(Th("Revista"), Th("Indexaciones"), Th("Resultado"))), Tbody(*filas),
                  cls="uk-table-divider uk-table-small"),
            cls="max-h-96 overflow-y-auto border border-border rounded-md mb-4"),
        Form(Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button(f"Cargar {len(listas)} revista(s)", type="submit", cls=ButtonT.primary, disabled=not listas),
                 cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/importar/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-4xl")


@rt(f"{BASE}/importar/confirmar")
def post(auth, sess, contenido: str = ""):
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return modal("Importar revistas", _form_archivo(["No se pudo leer el archivo. Súbalo otra vez."]))
    grupos, _ = importar_revistas.leer(datos)
    nuevas, completadas, n_idx = importar_revistas.aplicar(grupos, auth["id"])
    add_toast(sess, f"{nuevas} revista(s) nueva(s), {completadas} completada(s), {n_idx} indexación(es).", "success")
    return Redirect(BASE)


# Al final: /admin/revistas/{rid} capturaría rutas literales como /importar o /plantilla.
@rt(BASE + "/{rid}")
def get(auth, rid: int):
    r = revistas.obtener(rid)
    if not r:
        return pagina("No encontrada", P("Esa revista no existe."), usuario=auth)
    n = revistas.buscar(r["titulo"])
    n_prod = next((x["n_productos"] for x in n if x["id"] == rid), 0)
    datos = Card(
        Div(H3("Datos", cls="text-base font-semibold"),
            Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.ghost, ButtonT.sm),
                   hx_get=f"{BASE}/{rid}/editar", hx_target=f"#{ID_MODAL}"), cls="flex justify-between mb-2"),
        *[Div(Span(k, cls=(TextPresets.muted_sm, "w-40 shrink-0")), Span(v or "—"), cls="flex gap-2 py-1")
          for k, v in (("ISSN", r["issn"]), ("ISSN electrónico", r["eissn"]), ("País", r["pais"]),
                       ("Editorial", r["editorial"]), ("Revisión por pares", _si_no(r["arbitrada"])),
                       ("Acceso abierto", _si_no(r["acceso_abierto"])), ("Nota", r["nota"]))],
        Div(Span("Sitio web", cls=(TextPresets.muted_sm, "w-40 shrink-0")),
            A(r["url"], href=r["url"], target="_blank", rel="noopener", cls="text-primary hover:underline break-all")
            if r["url"] else Span("—"), cls="flex gap-2 py-1"))
    verificar = Button(UkIcon("badge-check", height=14, width=14), "Marcar como verificada", cls=ButtonT.primary,
                       hx_post=f"{BASE}/{rid}/verificar", hx_vals='{"verificada": "1"}') \
        if r["estado"] != "verificada" else \
        Button("Volver a pendiente", cls=(ButtonT.ghost, ButtonT.sm), hx_post=f"{BASE}/{rid}/verificar",
               hx_vals='{"verificada": "0"}',
               hx_confirm="Sus artículos volverán a usar lo declarado por los autores. ¿Continuar?")
    return pagina(
        r["titulo"],
        A(UkIcon("arrow-left", height=14, width=14), "Catálogo de revistas", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(insignia_estado(r), Span(f"{n_prod} producto(s) vinculado(s)", cls=TextPresets.muted_sm),
                cls="flex items-center gap-2"),
            Div(verificar,
                Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon), aria_label="Eliminar",
                       hx_delete=f"{BASE}/{rid}", hx_confirm="¿Eliminar esta revista del catálogo?")
                if not n_prod else "", cls="flex gap-2"),
            cls="flex flex-wrap items-center justify-between gap-2"),
        H2(r["titulo"], cls="mt-2 mb-1"),
        P(f"Verificada por la administración el {r['verificada_en'][:10]}." if r["estado"] == "verificada"
          else "Pendiente: mientras no se verifique, sus artículos usan lo que declararon los autores.",
          cls=(TextPresets.muted_sm, "mb-6")),
        Div(datos, tarjeta_indexaciones(r), cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        usuario=auth, seccion="revistas")
