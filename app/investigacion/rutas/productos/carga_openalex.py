"""Carga de la producción desde OpenAlex: búsqueda por ORCID, registro y descarte."""
import base64
import json
import re
from datetime import date

import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, Input, Option, P, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, CheckboxX, FormLabel, TextPresets, UkIcon

from app.investigacion import cosecha, importacion, perfiles
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.investigacion.rutas.productos.lista import EVENTO

rt = APIRouter()


# --- Carga desde OpenAlex ------------------------------------------------------------------------------

ID_COSECHA = "resultados-openalex"
ESTADO_COSECHA = {"nueva": ("Nueva", "azul"), "registrada": ("Ya registrada", "verde"),
                  "descartada": ("Descartada", "gris"), "no_aplica": ("No se importa", "gris")}


def fila_cosecha(c, uid):
    texto, tono = ESTADO_COSECHA[c["estado"]]
    d = c["datos"]
    detalle = " · ".join(str(x) for x in (c["tipo"] or c["motivo"], d.get("medio"), f"{c['citas']} citas") if x)
    accion = ""
    if c["estado"] == "registrada":
        accion = A("Ver", href=f"/productos/{c['existente']['id']}", cls="text-sm text-primary hover:underline") \
            if c["soy_autor"] else fh.Button("Sumarme como autor", type="button", cls="text-sm text-primary hover:underline",
                                             hx_post=f"/productos/{c['existente']['id']}/sumarme", hx_swap="none")
    elif c["estado"] in ("nueva", "descartada"):
        accion = fh.Button("Descartar" if c["estado"] == "nueva" else "Volver a proponer", type="button",
                           cls="text-sm text-muted-foreground hover:underline",
                           hx_post="/productos/openalex/descartar",
                           hx_vals=json.dumps({"openalex_id": c["openalex_id"], "titulo": d["titulo"][:300],
                                               "restaurar": "1" if c["estado"] == "descartada" else ""}),
                           hx_target=f"#oa-{c['openalex_id']}", hx_swap="outerHTML")
    return Div(
        CheckboxX(name="sel", value=c["openalex_id"], checked=c["estado"] == "nueva",
                  disabled=c["estado"] != "nueva", aria_label=f"Registrar {d['titulo']}"),
        Div(Div(Span(str(d.get("anio") or ""), cls="font-mono text-sm text-muted-foreground mr-2"),
                Span(d["titulo"], cls="font-medium"), cls="leading-snug"),
            P(detalle, cls=TextPresets.muted_sm),
            P(", ".join(f"{a['nombres']} {a['apellidos']}".strip() for a in c["autores"][:8])
              + ("…" if len(c["autores"]) > 8 else ""), cls="text-xs text-muted-foreground"),
            cls="min-w-0 flex-1"),
        Div(insignia(texto, tono), accion, cls="flex flex-col items-end gap-1 shrink-0"),
        id=f"oa-{c['openalex_id']}", cls="flex items-start gap-3 py-3")


def resultados_cosecha(res, uid, mensajes=()):
    lista = res["lista"]
    nuevas = [c for c in lista if c["estado"] == "nueva"]
    cuenta = {k: sum(c["estado"] == k for c in lista) for k in ESTADO_COSECHA}
    # Lo encontrado viaja de vuelta para registrar lo elegido sin volver a consultar OpenAlex.
    carga = base64.b64encode(json.dumps(nuevas, ensure_ascii=False).encode()).decode()
    return Div(
        *[Div(P(m, cls="text-sm"), cls="rounded-md border border-amber-300 bg-amber-50 text-amber-900 "
                                      "dark:bg-amber-950 dark:text-amber-200 p-3") for m in (*res["avisos"], *mensajes)],
        P(f"ORCID {res['orcid']}: {len(lista)} obra(s) · {cuenta['nueva']} nueva(s) · {cuenta['registrada']} ya "
          f"registrada(s) · {cuenta['descartada']} descartada(s) · {cuenta['no_aplica']} que no se importan.",
          cls="text-sm font-medium"),
        fh.Form(Input(type="hidden", name="carga", value=carga),
                Div(*[fila_cosecha(c, uid) for c in lista], cls="divide-y divide-border") if lista
                else P("OpenAlex no tiene obras con su ORCID en esos años.", cls=TextPresets.muted_sm),
                Div(P("Revise cada obra antes de registrarla: OpenAlex a veces atribuye obras por error. Se reconocen los "
                      "autores del instituto, la revista del catálogo y su filiación IIMAT/UMSA cuando la afiliación "
                      "publicada la menciona.", cls=TextPresets.muted_sm),
                    Button(UkIcon("download", height=14, width=14), "Registrar las seleccionadas", type="submit",
                           cls=ButtonT.primary, disabled=not nuevas),
                    cls="flex flex-wrap items-center justify-between gap-3 sticky bottom-0 bg-background border-t "
                        "border-border py-3") if nuevas else "",
                hx_post="/productos/openalex/registrar", hx_target=f"#{ID_COSECHA}", cls="space-y-3"),
        id=ID_COSECHA, cls="space-y-3")


@rt("/productos/openalex")
def get(auth):
    p = perfiles.obtener(auth["id"])
    desde, hasta = cosecha.anios_por_omision()
    anios = list(range(date.today().year, 1969, -1))
    return pagina(
        "Buscar mi producción",
        A(UkIcon("arrow-left", height=14, width=14), "Mis productos", href="/productos",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Buscar mi producción en OpenAlex"),
        P("OpenAlex es un catálogo abierto de publicaciones científicas. Con su ORCID, el sistema busca sus obras, "
          "le muestra cuáles faltan en el sistema y registra las que usted elija, con sus citas. Por omisión, los "
          "últimos 5 años (la ventana de evidencia de la acreditación).", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(fh.Form(
            Div(Span("ORCID: ", cls=TextPresets.muted_sm),
                Span(p["orcid"], cls="font-mono") if p and p["orcid"] else
                A("regístrelo en «Mi perfil»", href="/perfil", cls="text-primary hover:underline"),
                cls="text-sm"),
            Div(*[Div(FormLabel(t, fr=n), Select(*[Option(str(a), value=str(a), selected=a == v) for a in anios],
                                              id=n, name=n, cls="uk-select w-28"), cls="space-y-1")
                  for t, n, v in (("Desde", "desde", desde), ("Hasta", "hasta", hasta))],
                Button(UkIcon("search", height=14, width=14), "Buscar en OpenAlex", type="submit", cls=ButtonT.primary,
                       disabled=not (p and p["orcid"])),
                Span(UkIcon("loader-circle", height=16, width=16, cls="animate-spin"), id="buscando-oa",
                     cls="htmx-indicator"),
                cls="flex flex-wrap items-end gap-3"),
            hx_post="/productos/openalex/buscar", hx_target=f"#{ID_COSECHA}", hx_indicator="#buscando-oa",
            cls="space-y-3")),
        Div(id=ID_COSECHA, cls="mt-6"),
        usuario=auth, seccion="productos")


@rt("/productos/openalex/buscar")
def post(auth, desde: int = 0, hasta: int = 0):
    d, h = cosecha.anios_por_omision()
    desde, hasta = (desde or d), (hasta or h)
    if desde > hasta:
        desde, hasta = hasta, desde
    try:
        res = cosecha.candidatos(auth["id"], desde, hasta)
    except importacion.ErrorImportacion as e:
        return Div(mensaje_error(str(e)), id=ID_COSECHA)
    return resultados_cosecha(res, auth["id"])


@rt("/productos/openalex/registrar")
def post(auth, sess, carga: str = "", sel: list[str] = None):
    try:
        nuevas = json.loads(base64.b64decode(carga, validate=True).decode()) if carga else []
    except ValueError:
        return Div(mensaje_error("No se pudo leer la búsqueda. Vuelva a buscar."), id=ID_COSECHA)
    elegidas = [c for c in nuevas if c.get("openalex_id") in set(sel or [])]
    creados, mensajes = cosecha.registrar(auth["id"], elegidas)
    add_toast(sess, f"{creados} producto(s) registrado(s) desde OpenAlex.", "success")
    return (Div(Div(P(f"Se registraron {creados} producto(s). Revise en «Mis productos» su nivel de revisión y su "
                      "filiación, y vincúlelos a sus proyectos si corresponde.", cls="text-sm text-green-700"),
                    *[P(m, cls="text-sm text-amber-700") for m in mensajes],
                    A("Ir a mis productos", href="/productos", cls="text-sm text-primary hover:underline"),
                    cls="space-y-2 rounded-md border border-border p-4"), id=ID_COSECHA),
            HtmxResponseHeaders(trigger=EVENTO))


@rt("/productos/openalex/descartar")
def post(auth, openalex_id: str = "", titulo: str = "", restaurar: str = ""):
    if not re.fullmatch(r"W\d+", openalex_id):
        return Response(status_code=400)
    if restaurar:
        cosecha.restaurar(auth["id"], openalex_id)
        return Div(P(f"«{titulo}» se volverá a proponer en la próxima búsqueda.", cls=TextPresets.muted_sm),
                   id=f"oa-{openalex_id}", cls="py-3")
    cosecha.descartar(auth["id"], openalex_id, titulo)
    return Div(P(f"Descartada: «{titulo}». No se le volverá a proponer.", cls=TextPresets.muted_sm),
               id=f"oa-{openalex_id}", cls="py-3")
