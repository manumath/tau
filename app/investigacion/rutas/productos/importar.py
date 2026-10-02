"""Importación de un producto por DOI o arXiv y avisos de duplicado: si el producto ya está
registrado, se ofrece sumarse como autor en vez de registrarlo dos veces."""
from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, P, Response, Span
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, UkIcon

from app.investigacion import importacion, msc, productos
from app.comun.componentes.layout import ID_MODAL
from app.comun.db import auditar
from app.investigacion.rutas.productos.formulario import autores_de_refs, caja_importar, modal_form
from app.investigacion.rutas.productos.lista import EVENTO

rt = APIRouter()


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
    # Clasificación MSC2020 sugerida: la de zbMATH Open para el DOI; si no la hay, el área principal de
    # los autores del instituto.
    if (codigos := importacion.msc_de_zbmath(d.get("doi") or info.get("doi_publicado"))):
        d["msc"], d["_msc_origen"] = codigos, "zbMATH Open"
    else:
        d["msc"] = msc.sugeridos_por_perfil([int(r[2:]) for r in refs if r.startswith("i:")])
        d["_msc_origen"] = "el perfil de los autores"
    return modal_form(auth, d, autores_de_refs(refs, filiaciones), [], proyectos_sel=proyecto or [],
                       importado=info)


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



@rt("/productos/{pid}/sumarme")
def post(auth, sess, pid: int):
    p = productos.obtener(pid)
    if not p:
        return Response(status_code=404)
    productos.sumar_autor(pid, auth["id"])
    auditar(auth["id"], "sumarse_autor", "producto", pid)
    add_toast(sess, f"Ahora figura como autor(a) de «{p['titulo']}».", "success")
    return "", HtmxResponseHeaders(trigger=EVENTO)
