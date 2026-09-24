"""Directorio interno de investigadores, perfil de solo lectura y fotos."""
from fasthtml.common import (A, APIRouter, Div, FileResponse, FtResponse, HtmxResponseHeaders, Li,
                             P, Response, Span, Ul)
from monsterui.all import H2, Card, Grid, Input, TextPresets, UkIcon

from app import actividades, fotos, perfiles, productos
from app.components.layout import pagina
from app.components.registros import url_filtrada
from app.components.perfil import (avatar, chip_msc, lista_identificadores, seccion,
                                   texto_con_parrafos)

rt = APIRouter()

ID_RESULTADOS = "directorio-resultados"


def tarjeta(inv):
    subtitulo = " · ".join(x for x in (inv["cargo"], inv["unidad"]) if x)
    area = inv["area"]
    return A(Card(Div(
        avatar(inv, "size-14", "text-lg"),
        Div(Div(f"{inv['nombres']} {inv['apellidos']}", cls="font-semibold"),
            P(subtitulo, cls=TextPresets.muted_sm) if subtitulo else "",
            Div(Span(area["codigo"], cls="font-mono text-xs font-semibold mr-1 nomath"),
                Span(area["texto"], cls="text-xs"),
                cls="mt-1 text-muted-foreground") if area else "",
            cls="min-w-0"),
        cls="flex gap-4 items-center"), cls="h-full hover:shadow-md transition"),
        href=f"/investigadores/{inv['id']}", cls="block")


def resultados(texto):
    lista = perfiles.directorio(texto)
    if not lista:
        return Div(P("Nadie coincide con la búsqueda.", cls=(TextPresets.muted_sm, "py-6")),
                   id=ID_RESULTADOS)
    return Div(P(f"{len(lista)} investigador{'es' if len(lista) != 1 else ''}",
                 cls=(TextPresets.muted_sm, "mb-3")),
               Grid(*[tarjeta(i) for i in lista], cols_sm=1, cols_md=2, cols_lg=3, gap=4),
               id=ID_RESULTADOS)


@rt("/investigadores")
def get(auth, q: str = ""):
    return pagina(
        "Investigadores",
        Div(H2("Investigadores"),
            P("Directorio interno. Busque por nombre, unidad o área (código MSC como «11M» o tema "
              "como «graph»).", cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Input(type="search", name="q", value=q, placeholder="Buscar…", cls="max-w-md mb-6",
              aria_label="Buscar investigadores", hx_get="/investigadores/resultados",
              hx_target=f"#{ID_RESULTADOS}", hx_swap="outerHTML",
              hx_trigger="input changed delay:300ms, search"),
        resultados(q),
        usuario=auth, seccion="investigadores")


@rt("/investigadores/resultados")
def get(q: str = ""):
    # Mantiene la búsqueda en la URL de la página (no la del fragmento): se puede recargar o
    # compartir.
    return resultados(q), HtmxResponseHeaders(replace_url=url_filtrada("/investigadores", q=q))


def _produccion(uid):
    """Productos (primero los que cuentan para el informe) y actividades recientes."""
    prods = productos.de_investigador(uid)
    prods.sort(key=lambda x: (not productos.cuenta_para_informe(x), -x["anio"]))
    acts = actividades.de_investigador(uid)[:8]
    return Div(
        seccion("pub-productos", f"Productos ({len(prods)})",
                Ul(*[Li(A(productos.cita(x), href=f"/productos/{x['id']}", cls="hover:underline"),
                        Span(" ✓ informe", cls="text-xs text-green-600")
                        if productos.cuenta_para_informe(x) else "",
                        cls="text-sm py-1") for x in prods[:15]], cls="space-y-1")
                if prods else P("Sin productos registrados.", cls=TextPresets.muted_sm)),
        seccion("pub-actividades", "Actividades recientes",
                Ul(*[Li(Span(actividades.fechas_texto(a), cls=(TextPresets.muted_sm, "mr-2")),
                        A(a["titulo"], href=f"/actividades/{a['id']}", cls="hover:underline"),
                        cls="text-sm py-1") for a in acts])
                if acts else P("Sin actividades registradas.", cls=TextPresets.muted_sm)),
        cls="space-y-6")


@rt("/investigadores/{uid}")
def get(auth, uid: int):
    p = perfiles.obtener(uid)
    if not p or not p["activo"]:
        return FtResponse(pagina("No encontrado",
                                 P("Ese investigador no existe o su cuenta está inactiva."),
                                 usuario=auth), status_code=404)
    areas = perfiles.areas(uid)
    subtitulo = " · ".join(x for x in (p["grado"], p["cargo"], p["unidad"]) if x)
    propio = uid == auth["id"]
    return pagina(
        f"{p['nombres']} {p['apellidos']}",
        A(UkIcon("arrow-left", height=14, width=14), "Directorio", href="/investigadores",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(avatar(p, "size-28", "text-3xl"),
            Div(H2(f"{p['nombres']} {p['apellidos']}"),
                P(subtitulo, cls=TextPresets.muted_sm) if subtitulo else "",
                A(p["email"], href=f"mailto:{p['email']}", cls="text-sm text-primary hover:underline"),
                A(UkIcon("pencil", height=14, width=14), "Editar mi perfil", href="/perfil",
                  cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mt-2")
                if propio else "",
                cls="flex flex-col"),
            cls="flex flex-col sm:flex-row gap-6 items-center sm:items-start mb-8"),
        Div(seccion("pub-areas", "Áreas de investigación (MSC2020)",
                    Div(*[chip_msc(a, principal=bool(a["principal"])) for a in areas],
                        cls="flex flex-wrap gap-2") if areas
                    else P("Sin áreas declaradas.", cls=TextPresets.muted_sm)),
            seccion("pub-bio", "Resumen de investigación", texto_con_parrafos(p["bio"])),
            _produccion(uid),
            seccion("pub-ids", "Identificadores", lista_identificadores(p)),
            cls="space-y-6 max-w-3xl"),
        usuario=auth, seccion="investigadores")


@rt("/fotos/{uid}")
def get(uid: int):
    """Foto de perfil. Requiere sesión (pasa por la Beforeware); no es pública."""
    p = perfiles.obtener(uid)
    if not p or not p["foto"] or not fotos.ruta(p["foto"]).exists():
        return Response(status_code=404)
    # La URL lleva ?v=<archivo>, así que puede cachearse: al cambiar la foto cambia la URL.
    return FileResponse(fotos.ruta(p["foto"]), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})
