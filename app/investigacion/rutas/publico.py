"""Perfiles públicos (sin sesión) y API JSON de solo lectura.

Solo se publica a quien activó «Perfil público» en «Mi perfil» y tiene la cuenta activa. De ellos
se muestran nombre, grado, cargo, unidad, líneas de investigación vigentes, áreas MSC, resumen, identificadores, foto y productos
aceptados o publicados (sin presentaciones). Nunca: correo, actividades, proyectos, adjuntos ni
productos en curso.
"""
from fasthtml.common import (A, APIRouter, Div, FileResponse, Footer, Form, Header, Input, JSONResponse,
                             Li, Main, P, Redirect, Response, Span, Title, Ul)
from monsterui.all import H2, Card, Container, ContainerT, Grid, TextPresets, UkIcon

from app.comun import config, fotos
from app.investigacion import lineas, perfiles, productos
from app.investigacion.componentes.lineas import insignias_lineas
from app.investigacion.componentes.perfil import avatar, chip_msc, lista_identificadores, seccion, texto_con_parrafos
from app.comun.db import get_db
from app.investigacion.identificadores import IDENTIFICADORES

rt = APIRouter()

# --- Datos públicos ---------------------------------------------------------------------------------

def _lineas_vigentes(uid: int) -> list[dict]:
    return [x for x in lineas.de_investigador(uid) if lineas.vigente(x)]


def perfil_publico(uid: int) -> dict | None:
    p = perfiles.obtener(uid)
    return p if p and p["activo"] and p["perfil_publico"] else None


# Qué se publica: productos aceptados o publicados, salvo presentaciones (no son publicaciones).
FILTRO_PUBLICO = """p.estado_publicacion IN ('aceptado', 'publicado')
    AND p.tipo_id NOT IN (SELECT id FROM tipo_producto WHERE nombre = 'Presentación')"""


def productos_publicos(uid: int) -> list[dict]:
    filas = get_db().q(
        f"""SELECT DISTINCT p.id FROM producto p JOIN producto_autor pa ON pa.producto_id = p.id
            WHERE pa.investigador_id = ? AND {FILTRO_PUBLICO}
            ORDER BY p.anio DESC, p.id DESC""", [uid])
    return productos.sin_preprints_publicados(productos.obtener_varios(f["id"] for f in filas))


def ids_publicos() -> set[int]:
    return {f["usuario_id"] for f in get_db().q(
        """SELECT i.usuario_id FROM investigador i JOIN usuario u ON u.id = i.usuario_id
           WHERE i.perfil_publico = 1 AND u.activo = 1""")}


# --- Páginas ---------------------------------------------------------------------------------------------

def pagina_publica(titulo, *contenido):
    cabecera = Header(Container(Div(
        A(Div(UkIcon("sigma", height=24, width=24), Span(config.NOMBRE_INSTITUTO, cls="font-semibold"),
              cls="flex items-center gap-2"), href="/publico/investigadores"),
        Div(A("Investigadores", href="/publico/investigadores", cls="text-sm hover:underline"),
            A("Ingresar", href="/login", cls="uk-btn uk-btn-default uk-btn-sm"),
            cls="flex items-center gap-4"),
        cls="flex items-center justify-between py-3"), cls=ContainerT.xl), cls="border-b border-border")
    pie = Footer(Container(P(f"{config.NOMBRE_INSTITUTO} · Información publicada por cada investigador(a).",
                             cls=(TextPresets.muted_sm, "py-6")), cls=ContainerT.xl),
                 cls="border-t border-border mt-12")
    return (Title(f"{titulo} · {config.NOMBRE_INSTITUTO}"), cabecera,
            Main(Container(*contenido, cls=(ContainerT.xl, "py-8"))), pie)


def _cita_publica(p, publicos):
    """Autores del instituto con perfil público, enlazados; el resto, en texto."""
    autores = []
    for i, a in enumerate(p["autores"]):
        if i:
            autores.append(", ")
        nombre = f"{a['nombres']} {a['apellidos']}"
        autores.append(A(nombre, href=f"/publico/investigadores/{a['id']}", cls="text-primary hover:underline")
                       if a["interno"] and a["id"] in publicos else nombre)
    medio = ", ".join(str(x) for x in (p["medio"], p["volumen"] and f"vol. {p['volumen']}",
                                        p["paginas"] and f"pp. {p['paginas']}") if x)
    arxiv = productos.arxiv_de(p)
    enlace = f"https://doi.org/{p['doi']}" if p["doi"] else f"https://arxiv.org/abs/{arxiv}" if arxiv else p["url"]
    return Li(Div(Span(str(p["anio"]), cls="font-mono text-sm text-muted-foreground w-12 shrink-0"),
                  Div(A(p["titulo"], href=enlace, target="_blank", rel="noopener", cls="font-medium hover:underline")
                      if enlace else Span(p["titulo"], cls="font-medium"),
                      P(*autores, cls="text-sm"),
                      P(medio + (" · aceptado" if p["estado_publicacion"] == "aceptado" else ""),
                        cls=TextPresets.muted_sm) if medio else "",
                      P(A(f"arXiv:{arxiv}", href=f"https://arxiv.org/abs/{arxiv}", target="_blank", rel="noopener",
                          cls="text-primary hover:underline"), cls="text-sm") if arxiv and p["doi"] else "",
                      P("MSC2020: " + ", ".join(m["codigo"] for m in p["msc"]), cls=(TextPresets.muted_sm, "nomath"),
                        title=" · ".join(m["texto_plano"] for m in p["msc"])) if p["msc"] else "",
                      cls="min-w-0"),
                  cls="flex gap-4"), cls="py-3")


@rt("/publico")
def get():
    return Redirect("/publico/investigadores")


@rt("/publico/investigadores")
def get(q: str = ""):
    lista = perfiles.directorio(q, solo_publicos=True)
    tarjetas = [A(Card(Div(avatar(i, "size-14", "text-lg", ruta="/publico/fotos"),
                           Div(Div(f"{i['nombres']} {i['apellidos']}", cls="font-semibold"),
                               P(" · ".join(x for x in (i["cargo"], i["unidad"]) if x), cls=TextPresets.muted_sm),
                               Div(Span(i["area"]["codigo"], cls="font-mono text-xs font-semibold mr-1 nomath"),
                                   Span(i["area"]["texto"], cls="text-xs"), cls="mt-1") if i["area"] else "",
                               cls="min-w-0"),
                           cls="flex gap-4 items-center"), cls="h-full hover:shadow-md transition"),
                  href=f"/publico/investigadores/{i['id']}", cls="block") for i in lista]
    return pagina_publica(
        "Investigadores",
        H2("Investigadores"),
        P("Personas del instituto que publican su perfil. Busque por nombre, unidad o área (MSC2020).",
          cls=(TextPresets.muted_sm, "mb-4")),
        # GET simple: funciona sin JavaScript y la búsqueda queda en la URL.
        Form(Input(type="search", name="q", value=q, placeholder="Buscar…", cls="uk-input max-w-md",
                   aria_label="Buscar investigadores"),
             method="get", action="/publico/investigadores", cls="mb-6"),
        Grid(*tarjetas, cols_sm=1, cols_md=2, cols_lg=3, gap=4) if tarjetas
        else P("No hay perfiles públicos que coincidan.", cls=(TextPresets.muted_sm, "py-6")))


@rt("/publico/investigadores/{uid}")
def get(uid: int):
    p = perfil_publico(uid)
    if not p:
        return Response("Perfil no disponible.", status_code=404)
    areas = perfiles.areas(uid)
    prods = productos_publicos(uid)
    publicos = ids_publicos()
    return pagina_publica(
        f"{p['nombres']} {p['apellidos']}",
        Div(avatar(p, "size-28", "text-3xl", ruta="/publico/fotos"),
            Div(H2(f"{p['nombres']} {p['apellidos']}"),
                P(" · ".join(x for x in (p["grado"], p["cargo"], p["unidad"]) if x), cls=TextPresets.muted_sm)),
            cls="flex flex-col sm:flex-row gap-6 items-center sm:items-start mb-8"),
        Div(seccion("pub-lineas", "Líneas de investigación del instituto",
                    insignias_lineas(_lineas_vigentes(uid), vacio="—")) if _lineas_vigentes(uid) else "",
            seccion("pub-areas", "Áreas de investigación (MSC2020)",
                    Div(*[chip_msc(a, principal=bool(a["principal"])) for a in areas], cls="flex flex-wrap gap-2")
                    if areas else P("—", cls=TextPresets.muted_sm)),
            seccion("pub-bio", "Investigación", texto_con_parrafos(p["bio"], vacio="—")),
            seccion("pub-productos", f"Publicaciones ({len(prods)})",
                    Ul(*[_cita_publica(x, publicos) for x in prods], cls="divide-y divide-border") if prods
                    else P("—", cls=TextPresets.muted_sm)),
            seccion("pub-ids", "Identificadores y enlaces", lista_identificadores(p)),
            cls="space-y-6 max-w-3xl"))


@rt("/publico/fotos/{uid}")
def get(uid: int):
    p = perfil_publico(uid)
    if not p or not p["foto"] or not fotos.ruta(p["foto"]).exists():
        return Response(status_code=404)
    return FileResponse(fotos.ruta(p["foto"]), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


# --- API JSON de solo lectura -------------------------------------------------------------------------------

CABECERAS_API = {"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=300"}


def _json(datos, status=200):
    return JSONResponse(datos, status_code=status, headers=CABECERAS_API)


def _investigador_json(p, completo=False):
    d = {"id": p["id"], "nombres": p["nombres"], "apellidos": p["apellidos"], "grado": p.get("grado"),
         "cargo": p.get("cargo"), "unidad": p.get("unidad"),
         "url": f"{config.URL_BASE}/publico/investigadores/{p['id']}"}
    if completo:
        d["resumen"] = p["bio"]
        d["identificadores"] = {c: p[c] for c in IDENTIFICADORES if p.get(c)}
        d["areas_msc"] = [{"codigo": a["codigo"], "texto": a["texto_plano"], "principal": bool(a["principal"])}
                          for a in perfiles.areas(p["id"])]
        d["lineas_investigacion"] = [x["nombre"] for x in _lineas_vigentes(p["id"])]
        d["foto"] = f"{config.URL_BASE}/publico/fotos/{p['id']}" if p["foto"] else None
    return d


def _producto_json(p, publicos):
    return {"id": p["id"], "titulo": p["titulo"], "anio": p["anio"], "tipo": p["tipo"],
            "estado": p["estado_publicacion"], "revision": p["revision"],
            "indices": [i["nombre"] for i in p["indices"]], "medio": p["medio"], "volumen": p["volumen"],
            "numero": p["numero"], "paginas": p["paginas"], "doi": p["doi"], "arxiv": productos.arxiv_de(p),
            "msc": [{"codigo": m["codigo"], "texto": m["texto_plano"], "principal": bool(m["principal"])}
                    for m in p["msc"]],
            "autores": [{"nombre": f"{a['nombres']} {a['apellidos']}",
                         "investigador_id": a["id"] if a["interno"] and a["id"] in publicos else None}
                        for a in p["autores"]]}


@rt("/api/v1/investigadores")
def get(q: str = ""):
    return _json([_investigador_json(i) for i in perfiles.directorio(q, solo_publicos=True)])


@rt("/api/v1/investigadores/{uid}")
def get(uid: int):
    p = perfil_publico(uid)
    if not p:
        return _json({"error": "no encontrado"}, 404)
    publicos = ids_publicos()
    return _json({**_investigador_json(p, completo=True),
                  "productos": [_producto_json(x, publicos) for x in productos_publicos(uid)]})


@rt("/api/v1/productos")
def get(anio: str = ""):
    """Productos aceptados o publicados con al menos un autor de perfil público."""
    publicos = ids_publicos()
    if not publicos:
        return _json([])
    marcas = ",".join("?" * len(publicos))
    filtro, params = ("AND p.anio = ?", [int(anio)]) if anio.isdigit() else ("", [])
    filas = get_db().q(
        f"""SELECT DISTINCT p.id FROM producto p JOIN producto_autor pa ON pa.producto_id = p.id
            WHERE pa.investigador_id IN ({marcas}) AND {FILTRO_PUBLICO}
            {filtro} ORDER BY p.anio DESC, p.id DESC""", [*publicos, *params])
    lista = productos.sin_preprints_publicados(productos.obtener_varios(f["id"] for f in filas))
    return _json([_producto_json(p, publicos) for p in lista])
