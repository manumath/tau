"""Acceso abierto y datos de los productos (PLAN §69, etapa 2): la página propia, el formulario de declaración (modal) y los
componentes que usa la ficha del producto. Solo declaran quienes pueden editar el producto; la página es de la propia persona."""
from urllib.parse import urlencode

from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, Input, Option, P, Response, Select, Textarea
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, Form, TextPresets

from app.comun import formato
from app.comun.componentes.layout import ID_MODAL, campo, cerrar_modal, mensaje_error, modal, pagina
from app.investigacion import acceso_abierto as aa, productos
from app.investigacion.componentes.acceso import boton_declarar, insignias_acceso
from app.investigacion.rutas.productos.lista import EVENTO

rt = APIRouter()
PAGINA = "/investigacion/acceso-abierto"
ID_LISTA = "lista-acceso"


# --- Formulario -----------------------------------------------------------------------------------------------------------

def _select(nombre, opciones: dict, actual, vacio: str):
    return Select(Option(vacio, value=""), *[Option(t, value=k, selected=k == (actual or "")) for k, t in opciones.items()],
                  name=nombre, cls="uk-select h-9 text-sm")


def modal_acceso(p: dict, v: dict, errores=()):
    existe = aa.de_producto(p["id"]) is not None
    return modal(
        "Acceso abierto y datos",
        mensaje_error(*errores),
        P(f"«{p['titulo']}»", cls="font-medium mb-1"),
        P("Es una declaración suya: TAU no verifica los enlaces. Si el texto es abierto o está depositado, aparece como tal en su "
          "perfil público.", cls=(TextPresets.muted_sm, "mb-4")),
        Form(
            campo("¿Dónde se puede leer el texto?", _select("texto", aa.TEXTOS, v.get("texto"), "Elija…")),
            Div(campo("Versión depositada", _select("version", aa.VERSIONES, v.get("version"), "—"),
                      P("Solo si es una copia en un repositorio.", cls=TextPresets.muted_sm)),
                campo("Licencia", _select("licencia", aa.LICENCIAS, v.get("licencia"), "No la indico"),
                      P("Solo si es abierto o depositado.", cls=TextPresets.muted_sm)),
                cls="grid sm:grid-cols-2 gap-3"),
            campo("Enlace del texto", Input(name="enlace", value=v.get("enlace") or "", type="url", cls="uk-input h-9 text-sm",
                                            placeholder="https://…"),
                  P("Obligatorio si es abierto o depositado; opcional con embargo.", cls=TextPresets.muted_sm)),
            campo("Fin del embargo", Input(name="embargo_hasta", value=v.get("embargo_hasta") or "", type="date",
                                           cls="uk-input h-9 text-sm w-48"),
                  P("Solo con embargo.", cls=TextPresets.muted_sm)),
            Div(P("Datos y código", cls="text-sm font-medium"), cls="pt-2 border-t border-border"),
            campo("¿Están disponibles?", _select("datos", aa.DATOS, v.get("datos"), "No lo declaro")),
            campo("Enlace de los datos o del código", Input(name="datos_enlace", value=v.get("datos_enlace") or "", type="url",
                                                           cls="uk-input h-9 text-sm", placeholder="https://… o doi"),
                  P("Obligatorio si están publicados.", cls=TextPresets.muted_sm)),
            campo("Nota (opcional)", Textarea(v.get("nota") or "", name="nota", rows=2, maxlength=aa.LARGO_NOTA,
                                              cls="uk-textarea text-sm")),
            Div(Button("Quitar la declaración", type="button", cls=(ButtonT.ghost, ButtonT.sm, "text-destructive"),
                       hx_delete=f"/productos/{p['id']}/acceso",
                       hx_confirm="¿Quitar lo declarado de este producto? Quedará «sin declarar».") if existe else "",
                Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                Button("Guardar", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end gap-2 pt-2"),
            hx_post=f"/productos/{p['id']}/acceso", hx_target=f"#{ID_MODAL}", cls="space-y-3"),
        ancho="max-w-xl")


def _producto_editable(pid: int, uid: int):
    """(producto, None) si existe, se deposita y quien pide puede editarlo; si no, (None, respuesta)."""
    p = productos.obtener(pid)
    if not p:
        return None, Response("No encontrado", status_code=404)
    if not productos.puede_editar(p, uid) or not aa.aplica(p):
        return None, Response("No autorizado", status_code=403)
    return p, None


@rt("/productos/{pid}/acceso")
def get(auth, pid: int):
    p, error = _producto_editable(pid, auth["id"])
    if error:
        return error
    return modal_acceso(p, aa.de_producto(pid) or aa.sugerencia(p))


@rt("/productos/{pid}/acceso")
def post(auth, sess, pid: int, texto: str = "", version: str = "", enlace: str = "", licencia: str = "", embargo_hasta: str = "",
         datos: str = "", datos_enlace: str = "", nota: str = ""):
    p, error = _producto_editable(pid, auth["id"])
    if error:
        return error
    crudo = dict(texto=texto, version=version, enlace=enlace, licencia=licencia, embargo_hasta=embargo_hasta, datos=datos,
                 datos_enlace=datos_enlace, nota=nota)
    valores, errores = aa.validar(crudo)
    if errores:
        return modal_acceso(p, crudo, errores)
    aa.guardar(pid, valores, auth["id"])
    add_toast(sess, "Declaración guardada.", "success")
    return cerrar_modal(), HtmxResponseHeaders(trigger=EVENTO)


@rt("/productos/{pid}/acceso")
def delete(auth, sess, pid: int):
    p, error = _producto_editable(pid, auth["id"])
    if error:
        return error
    aa.quitar(pid, auth["id"])
    add_toast(sess, "Se quitó la declaración.", "success")
    return cerrar_modal(), HtmxResponseHeaders(trigger=EVENTO)


# --- Página propia -----------------------------------------------------------------------------------------------------

def _tarjeta(valor, texto: str):
    return Card(Div(str(valor), cls="text-2xl font-semibold"), Div(texto, cls=TextPresets.muted_sm), cls="p-4")


def _fila(f: dict):
    a = f if f["texto"] else None
    return Div(
        Div(str(f["anio"]), cls="font-mono text-sm text-muted-foreground w-12 shrink-0 pt-0.5"),
        Div(A(f["titulo"], href=f"/productos/{f['id']}", cls="block font-medium hover:underline"),
            Div(*insignias_acceso(a), cls="flex flex-wrap gap-1.5 mt-1"),
            P(" · ".join(x for x in (aa.VERSIONES.get(f["version"]), aa.LICENCIAS.get(f["licencia"]),
                                     f["embargo_hasta"] and f"embargo hasta el {formato.fecha(f['embargo_hasta'])}") if x),
              cls=TextPresets.muted_sm) if a and (f["version"] or f["licencia"] or f["embargo_hasta"]) else "",
            cls="min-w-0 flex-1"),
        boton_declarar({"id": f["id"], "titulo": f["titulo"]}, a),
        cls="flex items-start gap-3 py-2")


@rt(PAGINA)
def get(auth, estado: str = "", anio: str = ""):
    if not auth.get("es_investigador"):
        return Response("No autorizado", status_code=403)
    estado = estado if estado in aa.FILTROS else ""
    todos = aa.de_investigador(auth["id"])
    r = aa.resumen(todos)
    lista = aa.de_investigador(auth["id"], estado, anio)
    url = f"{PAGINA}?{urlencode({k: v for k, v in (('estado', estado), ('anio', anio)) if v})}"
    filtros = Form(
        Div(campo("Situación", Select(*[Option(t, value=k, selected=k == estado) for k, t in aa.FILTROS.items()],
                                     name="estado", cls="uk-select h-9 text-sm")),
            campo("Año", Select(Option("Todos", value=""), *[Option(str(y), value=str(y), selected=str(y) == anio)
                                                             for y in aa.anios_de(auth["id"])],
                                name="anio", cls="uk-select h-9 text-sm")),
            Button("Filtrar", type="submit", cls=(ButtonT.default, ButtonT.sm, "self-end")), cls="flex flex-wrap gap-3"),
        action=PAGINA, method="get", cls="mb-4")
    porcentaje = f"{round(100 * r['en_abierto'] / r['total'])} %" if r["total"] else "—"
    return pagina(
        "Acceso abierto y datos",
        H2("Acceso abierto y datos"),
        P("Sus productos aceptados o publicados y dónde se puede leer cada texto. Es una declaración suya: TAU no verifica los "
          "enlaces ni exige nada. Lo que declare como abierto o depositado aparece en su perfil público. Se piden los de los "
          f"últimos {aa.ANIOS_A_DECLARAR} años; los anteriores puede declararlos cuando quiera.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Div(_tarjeta(porcentaje, f"en acceso abierto ({r['en_abierto']} de {r['total']})"),
            _tarjeta(r["sin_declarar"], "sin declarar"),
            _tarjeta(r["embargo"], "en embargo"),
            _tarjeta(r["datos_publicados"], "con datos o código publicados"),
            cls="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6"),
        filtros,
        Div(Card(*[_fila(f) for f in lista], cls="divide-y divide-border") if lista
            else Card(P("No hay productos con esta selección.", cls="text-sm")),
            id=ID_LISTA, hx_get=url, hx_select=f"#{ID_LISTA}", hx_trigger=f"{EVENTO} from:body", hx_swap="outerHTML"),
        usuario=auth, seccion="investigacion")
