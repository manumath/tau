"""Piezas de los informes imprimibles y de sus descargas (PLAN §55 y §73): la hoja con membrete, la barra de controles, las
cifras y la respuesta de un archivo. Las usan los informes de investigación, de docencia, de estudiantes y de calidad.

Los informes son páginas pensadas para imprimir: en pantalla se ven como una hoja, y el botón «Imprimir / Guardar PDF»
usa el diálogo del navegador (así las fórmulas LaTeX salen con KaTeX)."""
from datetime import date, datetime

import fasthtml.common as fh
from fasthtml.common import A, Div, Option, P, Response, Select, Span, Style, Table, Tbody, Td, Th, Thead, Tr
from monsterui.all import Button, ButtonT, UkIcon

from app.comun import config, formato
from app.comun.componentes import recursos

ESTILO_IMPRESION = Style("""
.hoja { background: #fff; color: #18181b; font-family: "EB Garamond", Georgia, serif; font-size: 1.05rem;
        font-variant-numeric: lining-nums; }
/* Títulos y membrete con la letra de la marca; tablas, cifras y gráficos en sans: se leen mejor. */
.hoja h1, .hoja h2, .hoja h3, .hoja .membrete { font-family: Montserrat, ui-sans-serif, system-ui, sans-serif; }
.hoja table, .hoja .grafico, .hoja .cifra, .hoja .no-imprimir, .hoja .apagado.text-xs {
  font-family: ui-sans-serif, system-ui, sans-serif; font-size: .875rem; font-variant-numeric: tabular-nums; }
.hoja a { color: #273353; }
.hoja h1 { font-size: 1.6rem; font-weight: 700; line-height: 1.2; }
.hoja h2 { font-size: 1.15rem; font-weight: 700; margin-top: 1.75rem; padding-bottom: .25rem;
           border-bottom: 1px solid #d4d4d8; }
.hoja h3 { font-size: 1rem; font-weight: 600; margin-top: 1rem; }
.hoja .apagado { color: #52525b; }
.hoja table { width: 100%; border-collapse: collapse; font-size: .875rem; }
.hoja th, .hoja td { border-bottom: 1px solid #e4e4e7; padding: .35rem .5rem; text-align: left;
                     vertical-align: top; }
.hoja th { font-weight: 600; }
.hoja th.text-right, .hoja td.text-right { text-align: right; }
.hoja ol.citas { list-style: decimal; padding-left: 1.5rem; }
.hoja ol.citas li { margin: .35rem 0; }
.hoja .membrete { border-color: #be141b; }               /* rojo de la marca: acento del membrete (§55) */
.hoja .membrete-marca { height: 3.25rem; width: auto; }    /* ≈ 200 px de ancho: el manual pide al menos 100 */
.hoja .membrete-logo { height: 3.5rem; width: auto; }
.hoja .membrete-texto { color: #273353; }
@media print {
  @page { size: A4; margin: 16mm 15mm; }
  .monster-navbar, nav, .no-imprimir, #fh-toast-container, #modal { display: none !important; }
  html, body, main, .uk-container { background: #fff !important; padding: 0 !important; margin: 0 !important;
                                    max-width: none !important; }
  .hoja { box-shadow: none !important; border: 0 !important; padding: 0 !important; }
  .hoja, .hoja * { color: #000 !important; }
  .hoja a { text-decoration: none; }
  .hoja h2, .hoja h3 { break-after: avoid; }
  .hoja .membrete-marca { height: 13mm; }
  .hoja .membrete-logo { height: 14mm; }
  .hoja .membrete-texto { color: #273353 !important; }
  /* Tablas anchas: sin recorte del contenedor con desplazamiento; letra y relleno menores. */
  .hoja .overflow-x-auto { overflow: visible !important; }
  .hoja table, .hoja table * { font-size: 8pt !important; }
  .hoja th, .hoja td { padding: .25rem .3rem; }
  .hoja th { white-space: normal !important; }
  .hoja .membrete { border-color: #be141b !important; }
  .hoja li, .hoja tr, .hoja .grafico { break-inside: avoid; }
}
""")


def _selector_anio(nombre, valor, anios, etiqueta):
    return fh.Label(Span(etiqueta, cls="text-sm"),
                    Select(*[Option(str(a), value=str(a), selected=a == valor) for a in anios],
                           name=nombre, cls="uk-select w-28"),
                    cls="flex items-center gap-2")


def barra(filtros=(), descargas=()):
    """Barra de controles (no se imprime): filtros por GET, descargas y botón de impresión."""
    return Div(
        fh.Form(*filtros, Button("Aplicar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                method="get", cls="flex flex-wrap items-center gap-3") if filtros else Div(),
        Div(Div(*descargas,
                Button(UkIcon("printer", height=16, width=16), "Imprimir / Guardar PDF", type="button",
                       cls=ButtonT.primary, data_accion="imprimir"),
                cls="flex flex-wrap justify-end gap-2"),
            P("Para el PDF con membrete: destino «Guardar como PDF» y, en «Más opciones», desmarque "
              "«Encabezados y pies de página» del navegador.", cls="text-xs text-muted-foreground text-right"),
            cls="space-y-1"),
        cls="no-imprimir flex flex-wrap items-center justify-between gap-4 mb-6")


def descarga(texto, href):
    return A(UkIcon("download", height=14, width=14), texto, href=href,
             cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1")


def _cadena_css(texto: str) -> str:
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"').replace("<", "\\3c ").replace("\n", " ") + '"'


def membrete(instituto: bool = False):
    """Membrete oficial de la Carrera (hoja membretada del Manual de Identidad, PLAN.md §55): su marca a la
    izquierda y la universidad y la facultad; en los informes de investigación, el logo del IIMAT a la derecha."""
    universidad = Div(Div(config.UNIVERSIDAD, cls="uppercase tracking-wide"), Div(config.FACULTAD),
                      Div(config.NOMBRE_INSTITUTO, cls="font-medium") if instituto else "",
                      cls="membrete-texto text-right text-xs leading-snug")
    return Div(fh.Img(src=recursos.url("img/marca/logotipo.png"), alt=config.NOMBRE_CARRERA, cls="membrete-marca"),
               Div(universidad,
                   fh.Img(src=recursos.url("img/marca/instituto.png"), alt=f"Logo del {config.NOMBRE_INSTITUTO}",
                          cls="membrete-logo") if instituto and recursos.existe("img/marca/instituto.png") else "",
                   cls="flex items-center gap-4"),
               cls="membrete flex flex-wrap items-center justify-between gap-x-6 gap-y-2 pb-3 mb-6 border-b-2")   # en el teléfono, en dos filas


def hoja(*contenido, titulo: str = "", instituto: bool = False):
    """Hoja imprimible con membrete. Al imprimir, el pie de cada página lleva el título del informe
    y «Página X de Y» (cajas de margen de @page: Chrome y Edge; otros navegadores las omiten). Sin
    `titulo`, usa el del primer H1 del documento. `instituto`: informe de investigación (memoria, anexo, informe
    de proyecto), con el IIMAT en el membrete y en el pie."""
    if not titulo:
        h1 = next((c for c in contenido if getattr(c, "tag", None) == "h1"), None)
        titulo = "".join(x for x in h1.children if isinstance(x, str)) if h1 else ""
    unidad = f"{config.NOMBRE_CARRERA} · {config.NOMBRE_INSTITUTO}" if instituto else config.NOMBRE_CARRERA
    pie = Div(P(config.DIRECCION, cls="membrete-texto") if config.DIRECCION else "",
              P(f"Generado el {formato.fecha(date.today())}, {datetime.now():%H:%M} · {config.NOMBRE_SISTEMA} · {unidad}"),
              cls="apagado text-xs mt-10 pt-3 border-t border-zinc-200 space-y-1")
    izquierda = _cadena_css(f"{titulo} · " if titulo else "") + f" {_cadena_css(unidad)}"
    paginas = Style("@media print { @page { @bottom-left { content: " + izquierda + "; font: 8pt sans-serif; "
                    "color: #52525b; } @bottom-right { content: \"Página \" counter(page) \" de \" counter(pages); "
                    "font: 8pt sans-serif; color: #52525b; } } }")
    return Div(paginas, membrete(instituto), *contenido, pie,
               cls="hoja rounded-lg shadow-lg border border-border p-10 max-w-4xl mx-auto")


def _cifra(valor, texto, href=None):
    """Cifra destacada; con `href`, enlaza a los registros que la componen."""
    contenido = (Div(formato.numero(valor) if isinstance(valor, float) else str(valor), cls="text-2xl font-bold"), Div(texto, cls="apagado text-xs"))
    if href:
        return A(*contenido, href=href, cls="cifra block border border-zinc-200 rounded p-3 text-center hover:bg-zinc-50",
                 style="color: inherit")
    return Div(*contenido, cls="cifra border border-zinc-200 rounded p-3 text-center")


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _archivo(contenido: bytes, nombre: str, tipo: str):
    return Response(contenido, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"',
                             "Cache-Control": "private, no-store"})


def _tabla_conteo(titulo_col, datos: dict, etiquetas=None):
    return Table(Thead(Tr(Th(titulo_col), Th("Cantidad", cls="text-right"))),
                 Tbody(*[Tr(Td((etiquetas or {}).get(k, k)), Td(str(v), cls="text-right")) for k, v in datos.items()]))
