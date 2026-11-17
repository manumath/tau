"""Mis colaboraciones (PLAN §69, etapa 3): coautores y compañeros de proyecto de la propia persona. Solo lectura, derivada de lo
registrado; la persona sale de la sesión."""
from urllib.parse import urlencode

from fasthtml.common import A, APIRouter, Div, Input, Li, P, Response, Span, Table, Tbody, Td, Th, Thead, Tr, Ul
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, TextPresets, UkIcon

from app.comun import exportar
from app.comun.componentes.layout import campo, pagina
from app.comun.componentes.registros import insignia
from app.investigacion import coautores as co, productos
from app.investigacion.proyectos import ESTADOS, TIPOS

rt = APIRouter()
PAGINA = "/investigacion/coautores"


def _anio(valor: str) -> int | None:
    return int(valor) if valor.isdigit() and 1900 <= int(valor) <= 2200 else None


def _consulta(**kw) -> str:
    q = urlencode({k: v for k, v in kw.items() if v})
    return f"?{q}" if q else ""


def _tarjeta(valor, texto: str):
    return Card(Div(str(valor), cls="text-2xl font-semibold"), Div(texto, cls=TextPresets.muted_sm), cls="p-4")


def _anios_texto(c: dict) -> str:
    if not c["primero"]:
        return "—"
    return str(c["primero"]) if c["primero"] == c["ultimo"] else f"{c['primero']}–{c['ultimo']}"


def _fila(c: dict, filtros: dict):
    return Tr(Td(A(f"{c['apellidos']}, {c['nombres']}", href=f"{PAGINA}{_consulta(con=c['ref'], **filtros)}",
                   cls="font-medium text-primary hover:underline"),
                 insignia("Instituto", "azul") if c["interno"] else "", cls="py-2 pr-3"),
              Td(c["institucion"] or "—", cls="py-2 pr-3"), Td(c["pais"] or "—", cls="py-2 pr-3"),
              Td(str(c["n_productos"]), cls="py-2 pr-3 text-right"), Td(str(c["n_proyectos"]), cls="py-2 pr-3 text-right"),
              Td(_anios_texto(c), cls="py-2 whitespace-nowrap"))


def _conteos(titulo: str, pares: list[tuple[str, int]], vacio: str):
    return Card(H3(titulo, cls="text-base font-semibold mb-2"),
                Ul(*[Li(Span(k, cls="text-sm"), Span(str(n), cls="text-sm font-mono"), cls="flex justify-between gap-3 py-1")
                     for k, n in pares], cls="divide-y divide-border") if pares else P(vacio, cls=TextPresets.muted_sm))


def _detalle(auth, d: dict, filtros: dict):
    return pagina(
        f"Colaboración con {d['nombres']} {d['apellidos']}",
        A(UkIcon("arrow-left", height=14, width=14), "Mis colaboraciones", href=f"{PAGINA}{_consulta(**filtros)}",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"{d['nombres']} {d['apellidos']}"),
        P(" · ".join(x for x in (d["institucion"], d["pais"], "del instituto" if d["interno"] else "externo") if x),
          cls=(TextPresets.muted_sm, "mb-4")),
        Card(H3(f"Productos en común ({len(d['lista_productos'])})", cls="text-base font-semibold mb-2"),
             Ul(*[Li(A(p["titulo"], href=f"/productos/{p['id']}", cls="font-medium hover:underline"),
                     P(productos.cita(p), cls=TextPresets.muted_sm), cls="py-2") for p in d["lista_productos"]],
                cls="divide-y divide-border") if d["lista_productos"] else P("Ninguno.", cls=TextPresets.muted_sm)),
        Card(H3(f"Proyectos en común ({len(d['lista_proyectos'])})", cls="text-base font-semibold mb-2"),
             Ul(*[Li(A(p["nombre"], href=f"/proyectos/{p['id']}", cls="font-medium hover:underline"),
                     Span(f" · {TIPOS[p['tipo']]} · {ESTADOS[p['estado']]}", cls=TextPresets.muted_sm), cls="py-2")
                  for p in d["lista_proyectos"]], cls="divide-y divide-border")
             if d["lista_proyectos"] else P("Ninguno.", cls=TextPresets.muted_sm), cls="mt-4"),
        usuario=auth, seccion="investigacion")


@rt(PAGINA)
def get(auth, desde: str = "", hasta: str = "", con: str = ""):
    if not auth.get("es_investigador"):
        return Response("No autorizado", status_code=403)
    d, h = _anio(desde), _anio(hasta)
    filtros = {"desde": str(d) if d else "", "hasta": str(h) if h else ""}
    if con:
        detalle = co.compartidos(auth["id"], con, d, h)
        if not detalle:
            return Response("No encontrado", status_code=404)
        return _detalle(auth, detalle, filtros)
    lista = co.colaboradores(auth["id"], d, h)
    r = co.resumen(lista)
    formulario = Form(
        Div(campo("Desde el año", Input(name="desde", value=filtros["desde"], type="number", min="1900", max="2200",
                                        cls="uk-input h-9 text-sm w-28")),
            campo("Hasta el año", Input(name="hasta", value=filtros["hasta"], type="number", min="1900", max="2200",
                                        cls="uk-input h-9 text-sm w-28")),
            Button("Filtrar", type="submit", cls=(ButtonT.default, ButtonT.sm, "self-end")),
            A(UkIcon("download", height=14, width=14), "Descargar la lista (CSV)", href=f"{PAGINA}.csv{_consulta(**filtros)}",
              cls="inline-flex items-center gap-1 text-sm text-primary hover:underline self-end ml-auto"),
            cls="flex flex-wrap gap-3"),
        action=PAGINA, method="get", cls="mb-4")
    tabla = Table(Thead(Tr(*[Th(t, cls=f"py-2 pr-3 text-left text-xs font-medium text-muted-foreground {c}")
                             for t, c in (("Persona", ""), ("Institución", ""), ("País", ""), ("Productos", "text-right"),
                                          ("Proyectos", "text-right"), ("Años", ""))])),
                  Tbody(*[_fila(c, filtros) for c in lista], cls="divide-y divide-border"), cls="w-full text-sm")
    return pagina(
        "Mis colaboraciones",
        H2("Mis colaboraciones"),
        P("Con quién firmó productos y con quién compartió proyectos, según lo registrado en el sistema. Solo usted ve esta "
          "pantalla; no se guarda nada. Si falta alguien, falta registrar el producto o el proyecto, o la persona externa tiene "
          "el nombre escrito de otra forma.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        formulario,
        Div(_tarjeta(r["total"], "personas con quienes colaboró"),
            _tarjeta(r["externos"], f"externas al instituto ({r['internos']} del instituto)"),
            _tarjeta(r["n_paises_extranjeros"], "países extranjeros"),
            _tarjeta(r["n_instituciones"], "instituciones externas"),
            cls="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6"),
        P(UkIcon("triangle-alert", height=14, width=14, cls="inline mr-1"),
          f"A {r['sin_pais']} coautor(es) externo(s) no se les registró el país; no cuentan en los países. ",
          A("Completar los países", href="/personas/externos?sin_pais=1", cls="text-primary hover:underline"),
          cls="text-sm text-amber-800 dark:text-amber-300 mb-4") if r["sin_pais"] else "",
        Div(_conteos("Por país (personas)", r["paises"], "Sin datos."),
            _conteos("Instituciones externas más frecuentes (personas)", r["instituciones"], "Sin datos."),
            cls="grid md:grid-cols-2 gap-4 mb-6"),
        Card(tabla, cls="overflow-x-auto") if lista else Card(P("Aún no hay coautores ni compañeros de proyecto "
                                                                "en el periodo elegido.", cls="text-sm")),
        usuario=auth, seccion="investigacion")


@rt(f"{PAGINA}.csv")
def get(auth, desde: str = "", hasta: str = ""):
    if not auth.get("es_investigador"):
        return Response("No autorizado", status_code=403)
    columnas = list(co.filas_csv([{"apellidos": "", "nombres": "", "institucion": "", "pais": "", "interno": True,
                                   "n_productos": 0, "n_proyectos": 0, "primero": None, "ultimo": None}])[0])
    contenido = exportar.a_csv(co.filas_csv(co.colaboradores(auth["id"], _anio(desde), _anio(hasta))), columnas)
    return Response(contenido, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="colaboraciones-tau.csv"'})

