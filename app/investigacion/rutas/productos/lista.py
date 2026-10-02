"""Lista de productos: presentación de cada producto, filtros y declaración de filiación."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, Label, Option, P, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, CheckboxX, TextPresets, UkIcon

from app.investigacion import filiacion, productos, proyectos
from app.comun.componentes.layout import ID_MODAL, pagina
from app.comun.componentes.registros import enlace_persona, filtros, insignia, url_filtrada
from app.investigacion.componentes.registros import insignias_proyectos
from app.comun.db import auditar

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
    if p.get("publicado_como"):
        res.append(insignia("Con versión publicada", "verde", icono="link", titulo=p["publicado_como"]["titulo"]))
    if p.get("msc"):
        principal = p["msc"][0]
        res.append(insignia(f"MSC {principal['codigo']}", "gris", titulo=principal["texto_plano"]))
    if p.get("citas"):
        res.append(insignia(f"{p['citas']} cita{'s' if p['citas'] != 1 else ''}", "gris", icono="quote",
                            titulo=f"Según OpenAlex, al {p['citas_actualizadas']}"))
    return Div(*res, cls="flex flex-wrap gap-1.5")


MARCAS_FILIACION = {1: ("✓", "text-green-700", "Firmó con la filiación del instituto (IIMAT/UMSA)"),
                    0: ("✗", "text-muted-foreground", "No firmó con la filiación del instituto"),
                    None: ("?", "text-amber-600", "Filiación sin declarar")}


def autores_texto(p):
    """Autores; los del instituto con una marca de filiación (✓ firmó, ✗ no, ? sin declarar)."""
    partes = []
    for i, a in enumerate(p["autores"]):
        if i:
            partes.append(", ")
        partes.append(enlace_persona(a, "font-medium" if a["interno"] else ""))
        if a["interno"]:
            marca, clase, titulo = MARCAS_FILIACION[a.get("filiacion")]
            partes.append(fh.Sup(marca, title=titulo, aria_label=titulo, cls=f"{clase} ml-0.5"))
    return Span(*partes, cls="text-sm")


def declarar_filiacion(p, uid):
    """Si el usuario es autor y no ha declarado su filiación: botones Sí / No en la lista."""
    propio = next((a for a in p["autores"] if a["interno"] and a["id"] == uid), None)
    if not propio or propio.get("filiacion") is not None or p["revision"] not in filiacion.REVISIONES_QUE_CUENTAN:
        return ""
    boton = lambda texto, valor: fh.Button(  # noqa: E731
        texto, type="button", cls="text-xs px-2 py-0.5 rounded border border-border hover:bg-muted",
        hx_post=f"/productos/{p['id']}/filiacion", hx_vals=f'{{"valor": "{valor}"}}',
        hx_target=f"#producto-{p['id']}", hx_swap="outerHTML")
    return Div(Span("¿Firmó con IIMAT/UMSA?", cls="text-xs text-amber-700"), boton("Sí", 1), boton("No", 0),
               cls="flex items-center gap-2")


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
            declarar_filiacion(p, uid),
            cls="min-w-0 flex-1 space-y-1"),
        acciones,
        id=f"producto-{p['id']}", cls="flex gap-4 py-4")


def _confirmacion_eliminar(p):
    otros = [a for a in p["autores"] if a["interno"]]
    aviso = " También desaparecerá del perfil de sus coautores del instituto." if len(otros) > 1 else ""
    return f"¿Eliminar «{p['titulo']}»?{aviso}"


def lista(uid, q="", anio="", tipo="", informe=False, sin_filiacion=False, area=""):
    items = productos.de_investigador(uid, q, anio, tipo, informe, sin_filiacion, area)
    n_informe = sum(productos.cuenta_para_informe(p) for p in items)
    contenido = (
        [P(f"{len(items)} producto{'s' if len(items) != 1 else ''} · {n_informe} cuenta"
           f"{'n' if n_informe != 1 else ''} para el informe del instituto",
           cls=TextPresets.muted_sm),
         Div(P("Declare si firmó cada uno con la filiación del instituto (IIMAT, CMAT, FCPN o UMSA; vale la "
               "doble filiación). Lo anterior a su ingreso no cuenta para el instituto, aunque lo declare.",
               cls="text-sm"),
             Button("Firmé todos estos con IIMAT/UMSA", type="button", cls=(ButtonT.default, ButtonT.sm),
                    hx_post="/productos/filiacion/todos", hx_include=f"#{ID_FILTROS}", hx_target=f"#{ID_LISTA}",
                    hx_swap="outerHTML", hx_confirm=f"¿Declarar que firmó con la filiación del instituto los "
                                                    f"{len(items)} productos de esta lista?"),
             cls="flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300 "
                 "bg-amber-50 dark:bg-amber-950 p-3 mt-3") if sin_filiacion else "",
         Div(*[item(p, uid) for p in items], cls="divide-y divide-border")]
        if items else [P("No hay productos que coincidan." if (q or anio or tipo or informe or sin_filiacion or area)
                         else "Aún no registra productos. Use «Nuevo producto» para empezar.",
                         cls=(TextPresets.muted_sm, "py-8 text-center"))])
    return Div(*contenido, id=ID_LISTA, hx_get="/productos/lista", hx_include=f"#{ID_FILTROS}",
               hx_trigger=f"{EVENTO} from:body", hx_swap="outerHTML")


# --- Rutas: lista ---------------------------------------------------------------------

def selector_area(areas, area):
    """Filtro por sección MSC2020 (en el código principal o en uno secundario)."""
    return Select(Option("Todas las áreas (MSC)", value=""),
                  *[Option(f"{s['codigo'][:2]} · {s['texto_plano']}", value=s["codigo"][:2], selected=s["codigo"][:2] == area)
                    for s in areas],
                  name="area", cls="uk-select w-56", aria_label="Área MSC2020")


@rt("/productos")
def get(auth, q: str = "", anio: str = "", tipo: str = "", informe: bool = False, sin_filiacion: bool = False,
        area: str = ""):
    uid = auth["id"]
    casilla_informe = Label(CheckboxX(name="informe", value="1", checked=informe),
                            Span("Solo los que cuentan para el informe"),
                            cls="flex items-center gap-2 text-sm")
    n_pend = filiacion.pendientes(uid)
    casilla_filiacion = Label(CheckboxX(name="sin_filiacion", value="1", checked=sin_filiacion),
                              Span(f"Sin filiación declarada ({n_pend})", cls="text-amber-700" if n_pend else ""),
                              cls="flex items-center gap-2 text-sm")
    return pagina(
        "Mis productos",
        Div(Div(H2("Mis productos"),
                P("Artículos, libros, reportes, presentaciones y más. Un producto con varios autores "
                  "del instituto se registra una sola vez y aparece en el perfil de cada uno.",
                  cls=TextPresets.muted_sm)),
            Div(A(UkIcon("download", height=16, width=16), "Exportar BibTeX", href="/productos/bibtex",
                  # Exporta lo que se ve: agrega los filtros vigentes (están en la URL de la página).
                  data_accion="con-busqueda",
                  cls="uk-btn uk-btn-default inline-flex items-center gap-1"),
                Button(UkIcon("file-up", height=16, width=16), "Importar BibTeX", cls=ButtonT.default,
                       hx_get="/productos/importar-bibtex", hx_target=f"#{ID_MODAL}"),
                A(UkIcon("scan-search", height=16, width=16), "Buscar en OpenAlex", href="/productos/openalex",
                  cls="uk-btn uk-btn-default inline-flex items-center gap-1",
                  title="Buscar su producción por ORCID y registrar la que falta"),
                Button(UkIcon("plus", height=16, width=16), "Nuevo producto", cls=ButtonT.primary,
                       hx_get="/productos/nuevo", hx_target=f"#{ID_MODAL}"),
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        filtros(ID_FILTROS, "/productos/lista", ID_LISTA, q, anio, productos.anios_de(uid), tipo,
                productos.tipos(todos=True), extra=[selector_area(productos.areas_de(uid), area), casilla_informe,
                                          casilla_filiacion]),
        Card(lista(uid, q, anio, tipo, informe, sin_filiacion, area)),
        usuario=auth, seccion="productos")


@rt("/productos/lista")
def get(auth, q: str = "", anio: str = "", tipo: str = "", informe: bool = False, sin_filiacion: bool = False,
        area: str = ""):
    return (lista(auth["id"], q, anio, tipo, informe, sin_filiacion, area),
            HtmxResponseHeaders(replace_url=url_filtrada("/productos", q=q, anio=anio, tipo=tipo, area=area,
                                                         informe="1" if informe else "",
                                                         sin_filiacion="1" if sin_filiacion else "")))


@rt("/productos/filiacion/todos")
def post(auth, sess, q: str = "", anio: str = "", tipo: str = "", informe: bool = False, area: str = ""):
    """Declara la filiación propia en todos los productos pendientes que muestra la lista."""
    uid = auth["id"]
    ids = [p["id"] for p in productos.de_investigador(uid, q, anio, tipo, informe, sin_filiacion=True, area=area)]
    n = filiacion.declarar(uid, ids, 1)
    auditar(uid, "declarar_filiacion", "producto", None, f"{n} producto(s)")
    add_toast(sess, f"Filiación declarada en {n} producto(s).", "success")
    return lista(uid, q, anio, tipo, informe, sin_filiacion=True, area=area)


@rt("/productos/{pid}/filiacion")
def post(auth, pid: int, valor: str = ""):
    """El autor declara su propia filiación en un producto (Sí / No desde la lista)."""
    p = productos.obtener(pid)
    if not p or not productos.es_autor(pid, auth["id"]) or valor not in ("0", "1"):
        return Response("No autorizado", status_code=403)
    filiacion.declarar(auth["id"], [pid], int(valor))
    return item(productos.obtener(pid), auth["id"])
