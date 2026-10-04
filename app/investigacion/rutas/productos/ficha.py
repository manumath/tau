"""Ficha de un producto."""
from fasthtml.common import A, APIRouter, Div, H3, P, Redirect, Span
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import permisos
from app.investigacion import actividades, lineas, productos, proyectos, revistas
from app.investigacion.componentes.lineas import insignias_lineas
from app.investigacion.componentes.msc import chips as chips_msc
from app.comun.componentes.layout import ID_MODAL, pagina
from app.comun.componentes.registros import dato, enlace_persona, insignia
from app.investigacion.componentes.registros import insignias_proyectos, seccion_adjuntos
from app.investigacion.rutas.productos.lista import EVENTO, _confirmacion_eliminar, insignias

rt = APIRouter()


# --- Ficha -------------------------------------------------------------------------------

def insignia_estado_revista(r):
    return insignia("verificada", "verde", icono="badge-check") if r["estado"] == "verificada" \
        else insignia("pendiente de verificar", "ambar", icono="clock")


def version_publicada(p, editable):
    """En un preprint: su versión publicada (con «Desenlazar») o el botón para enlazarla (PLAN.md §46)."""
    pub = p["publicado_como"]
    if pub:
        return Div(A(pub["titulo"], href=f"/productos/{pub['id']}", cls="text-primary hover:underline"),
                   Span(f"({pub['anio']})", cls=(TextPresets.muted_sm, "ml-1")),
                   Button("Desenlazar", type="button", cls=(ButtonT.ghost, ButtonT.xs, "ml-2"),
                          hx_delete=f"/productos/{p['id']}/version")  # sin confirmación: el aviso ofrece «Deshacer»
                   if editable else "", cls="flex flex-wrap items-center")
    if not editable:
        return None
    return Button(UkIcon("link", height=14, width=14), "Enlazar con su versión publicada", type="button",
                  cls=(ButtonT.default, ButtonT.sm), hx_get=f"/productos/{p['id']}/version", hx_target=f"#{ID_MODAL}")


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
            dato("Publicación", f"{productos.MESES[p['mes'] - 1]} {p['anio']}" if p["mes"] else str(p["anio"])),
            dato("Estado", productos.ESTADOS[p["estado_publicacion"]]),
            dato("Citas", f"{p['citas']} (según OpenAlex, al {p['citas_actualizadas']})"
                 if p.get("citas") is not None else None),
            dato("Medio", ", ".join(x for x in (p["medio"], p["volumen"] and f"vol. {p['volumen']}",
                                                p["numero"] and f"n.º {p['numero']}",
                                                p["paginas"] and f"pp. {p['paginas']}") if x)),
            dato("Revista del catálogo", Span(p["revista"]["titulo"],
                                              Span(" · " + " / ".join(x for x in (p["revista"]["issn"], p["revista"]["eissn"]) if x),
                                                   cls="font-mono text-xs") if p["revista"]["issn"] or p["revista"]["eissn"] else "",
                                              " ", insignia_estado_revista(p["revista"]))
                 if p["revista"] else None),
            dato("Nivel de revisión", Span(productos.REVISIONES[p["revision"]]
                                           + (f" ({', '.join(i['nombre'] for i in p['indices'])})" if p["indices"] else ""),
                                           Span(" · según el catálogo" if p["clasificacion_catalogo"] else
                                                " · declarado por los autores" if p["tipo"] == revistas.TIPO_ARTICULO else "",
                                                cls=TextPresets.muted_sm))),
            dato("Versión publicada", version_publicada(p, editable)) if productos.es_preprint(p) else "",
            dato("Preprint", A(p["preprint"]["titulo"], href=f"/productos/{p['preprint']['id']}",
                               cls="text-primary hover:underline") if p["preprint"] else None),
            dato("Clasificación MSC2020", chips_msc(p["msc"]) if p["msc"] else None),
            dato("Presentada en", A(actividad["titulo"], href=f"/actividades/{actividad['id']}",
                                    cls="text-primary hover:underline") if actividad else None),
            dato("Identificadores", Div(*[e for e in enlaces if e], cls="flex gap-4 flex-wrap"))
            if any(enlaces) else "",
            dato("Proyectos", Div(*insignias_proyectos(proyectos.vinculos_de("producto", p["id"])),
                                  cls="flex flex-wrap gap-1.5")
                 if proyectos.vinculos_de("producto", p["id"]) else None),
            dato("Líneas de investigación", insignias_lineas(lin) if (lin := lineas.de_registro("producto", p["id"]))
                 else None),
            dato("Cita", P(productos.cita(p), cls="text-sm")),
        ),
        Card(H3("Resumen", cls="text-base font-semibold mb-2"),
             P(p["resumen"], cls="whitespace-pre-line leading-relaxed")) if p["resumen"] else "",
        Card(H3("Archivos adjuntos", cls="text-base font-semibold mb-2"),
             seccion_adjuntos("producto", p["id"], editable)) if editable or permisos.puede(auth, "ver_evidencias") else "",
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
