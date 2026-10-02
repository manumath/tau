"""Campos del formulario de productos que dependen del tipo: revista del catálogo (en artículos),
nivel de revisión, índices y actividad asociada (en presentaciones). Se vuelven a pedir al servidor
cuando cambia el tipo, el año, la revisión o la revista (/productos/campos). También el buscador de
la clasificación MSC2020 (/productos/msc/…)."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Input, Label, Li, Option, P, Select, Span, Ul
from monsterui.all import CheckboxX, FormLabel, LabelInput, TextPresets, UkIcon

from app.investigacion import actividades, productos, revistas
from app.investigacion import msc as msc_mod
from app.investigacion.componentes import msc as msc_ui
from app.comun.componentes.registros import insignia

rt = APIRouter()

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
              hx_target="#resultados-revista", data_enter="prevenir"),
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


# --- Rutas ------------------------------------------------------------------------------

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


@rt("/productos/msc/buscar")
def get(msc_q: str = "", msc: list[str] = None):
    """Autocompletar de la clasificación MSC2020 (excluye los códigos ya elegidos)."""
    elegidos = msc or []
    if not msc_q.strip():
        return ""
    if len(elegidos) >= msc_mod.MAX_PRODUCTO:
        return msc_ui.resultados([], None, vacio=f"Ya tiene {msc_mod.MAX_PRODUCTO} códigos: quite uno para agregar otro.")
    return msc_ui.resultados(msc_mod.buscar(msc_q, excluir=tuple(elegidos)), lambda m: dict(
        hx_get=f"/productos/msc/fila?codigo={m['codigo']}", hx_target=f"#{msc_ui.LISTA}", hx_swap="beforeend",
        data_tras_pedido_limpiar=f"{msc_ui.BUSCAR},{msc_ui.RESULTADOS}"))


@rt("/productos/msc/fila")
def get(codigo: str = ""):
    m = msc_mod.por_codigo(codigo.strip())
    return msc_ui.fila(m) if m else ""
