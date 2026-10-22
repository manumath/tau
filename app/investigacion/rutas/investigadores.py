"""Directorio interno de investigadores, perfil de solo lectura y fotos."""
from fasthtml.common import (A, APIRouter, Div, FileResponse, FtResponse, HtmxResponseHeaders, Li,
                             Option, P, Response, Select, Span, Ul)
from monsterui.all import H2, Card, Grid, Input, TextPresets, UkIcon

from app.investigacion import actividades, lineas, perfiles, productos
from app.comun import fotos, permisos, vinculos
from app.investigacion.componentes.lineas import insignias_lineas
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import url_filtrada
from app.investigacion.componentes.perfil import avatar, chip_msc, lista_identificadores, seccion, texto_con_parrafos

rt = APIRouter()

ID_RESULTADOS = "directorio-resultados"


def etiqueta_categoria(categoria):
    if not categoria:
        return ""
    return Span(perfiles.CATEGORIAS[categoria],
                cls="inline-block rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground")


def tarjeta(inv):
    subtitulo = " · ".join(x for x in (inv["cargo"], inv["unidad"]) if x)
    area = inv["area"]
    return A(Card(Div(
        avatar(inv, "size-14", "text-lg"),
        Div(Div(Span(f"{inv['nombres']} {inv['apellidos']}", cls="font-semibold"),
                etiqueta_categoria(inv["categoria"]), cls="flex flex-wrap items-center gap-2"),
            P(subtitulo, cls=TextPresets.muted_sm) if subtitulo else "",
            Div(Span(area["codigo"], cls="font-mono text-xs font-semibold mr-1 nomath"),
                Span(area["texto"], cls="text-xs"),
                cls="mt-1 text-muted-foreground") if area else "",
            cls="min-w-0"),
        cls="flex gap-4 items-center"), cls="h-full hover:shadow-md transition"),
        href=f"/investigadores/{inv['id']}", cls="block")


def resultados(texto, categoria=""):
    lista = perfiles.directorio(texto, categoria=categoria)
    if not lista:
        return Div(P("Nadie coincide con la búsqueda.", cls=(TextPresets.muted_sm, "py-6")),
                   id=ID_RESULTADOS)
    return Div(P(f"{len(lista)} investigador{'es' if len(lista) != 1 else ''}",
                 cls=(TextPresets.muted_sm, "mb-3")),
               Grid(*[tarjeta(i) for i in lista], cols_sm=1, cols_md=2, cols_lg=3, gap=4),
               id=ID_RESULTADOS)


def _categoria_valida(categoria):
    return categoria if categoria in perfiles.CATEGORIAS or categoria == "sin" else ""


@rt("/investigadores")
def get(auth, q: str = "", categoria: str = ""):
    categoria = _categoria_valida(categoria)
    filtros = dict(hx_get="/investigadores/resultados", hx_target=f"#{ID_RESULTADOS}",
                   hx_swap="outerHTML", hx_include="#filtros-directorio")
    return pagina(
        "Investigadores",
        Div(Div(A(UkIcon("graduation-cap", height=14, width=14), "Estudiantes y tesistas", href="/estudiantes",
                  cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
                A(UkIcon("globe", height=14, width=14), "Coautores externos", href="/personas/externos",
                  cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
                cls="float-right flex gap-4"),
            H2("Investigadores"),
            P("Directorio interno. Busque por nombre, unidad o área (código MSC como «11M» o tema "
              "como «graph»).", cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Div(Input(type="search", name="q", value=q, placeholder="Buscar…", cls="max-w-md",
                  aria_label="Buscar investigadores", hx_trigger="input changed delay:300ms, search",
                  **filtros),
            Select(Option("Todas las categorías", value=""),
                   *[Option(t, value=c, selected=c == categoria) for c, t in perfiles.CATEGORIAS.items()],
                   *([Option("Sin categoría", value="sin", selected=categoria == "sin")]
                     if permisos.puede(auth, "ver_usuarios") else []),
                   name="categoria", aria_label="Filtrar por categoría", cls="uk-select w-56",
                   hx_trigger="change", **filtros),
            id="filtros-directorio", cls="flex flex-wrap gap-3 mb-6"),
        resultados(q, categoria),
        usuario=auth, seccion="investigadores")


@rt("/investigadores/resultados")
def get(q: str = "", categoria: str = ""):
    # Mantiene la búsqueda en la URL de la página (no la del fragmento): se puede recargar o
    # compartir.
    categoria = _categoria_valida(categoria)
    return (resultados(q, categoria),
            HtmxResponseHeaders(replace_url=url_filtrada("/investigadores", q=q, categoria=categoria)))


def _produccion(uid):
    """Productos (primero los que cuentan para el informe) y actividades recientes."""
    prods = productos.buscar(uid)
    prods.sort(key=lambda x: (not productos.cuenta_para_informe(x), -x["anio"]))
    primeros = productos.obtener_varios(x["id"] for x in prods[:15])  # solo se arman los que se muestran
    acts = actividades.de_investigador(uid)[:8]
    return Div(
        seccion("pub-productos", f"Productos ({len(prods)})",
                Ul(*[Li(A(productos.cita(x), href=f"/productos/{x['id']}", cls="hover:underline"),
                        Span(" ✓ informe", cls="text-xs text-green-600")
                        if productos.cuenta_para_informe(x) else "",
                        cls="text-sm py-1") for x in primeros], cls="space-y-1")
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
            Div(Div(H2(f"{p['nombres']} {p['apellidos']}"), etiqueta_categoria(p["categoria"]),
                    cls="flex flex-wrap items-center gap-3"),
                P(subtitulo, cls=TextPresets.muted_sm) if subtitulo else "",
                P(vinculos.resumen(uid) or "", cls=TextPresets.muted_sm),
                A(p["email"], href=f"mailto:{p['email']}", cls="text-sm text-primary hover:underline"),
                Div(A(UkIcon("pencil", height=14, width=14), "Editar mi perfil", href="/perfil",
                      cls="inline-flex items-center gap-1 text-sm text-primary hover:underline")
                    if propio else "",
                    A(UkIcon("file-user", height=14, width=14), "Ver CV",
                      href="/informes/cv" if propio else f"/informes/cv?uid={uid}",
                      cls="inline-flex items-center gap-1 text-sm text-primary hover:underline")
                    if propio or permisos.puede(auth, "ver_cv_ajeno") else "",
                    cls="flex gap-4 mt-2"),
                cls="flex flex-col"),
            cls="flex flex-col sm:flex-row gap-6 items-center sm:items-start mb-8"),
        Div(seccion("pub-lineas", "Líneas de investigación del instituto",
                    insignias_lineas([x for x in lineas.de_investigador(uid) if lineas.vigente(x)],
                                     vacio="No se adscribe a ninguna línea.")),
            seccion("pub-areas", "Áreas de investigación (MSC2020)",
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
