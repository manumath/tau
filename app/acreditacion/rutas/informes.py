"""Informes: CV del investigador, informe de proyecto y memoria anual del instituto.

Los informes son páginas pensadas para imprimir: en pantalla se ven como una hoja, y el botón
«Imprimir / Guardar PDF» usa el diálogo del navegador (así las fórmulas LaTeX salen con KaTeX,
cosa que un generador de PDF en el servidor no haría). La memoria y el informe de proyecto se
descargan además en XLSX y CSV.
"""
from datetime import date, datetime

from urllib.parse import urlencode

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, H1, H2, H3, HtmxResponseHeaders, Li, Ol, Option, P, Response, Select,
                             Span, Strong, Style, Table, Tbody, Td, Th, Thead, Tr, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Card, TextPresets, UkIcon

from app.investigacion import (actividades, cosecha, importacion, institucionales, perfiles, productos, proyectos,
                               revistas)
from app.comun import config, permisos, unidades
from app.comun.componentes import recursos
from app.acreditacion import informes, programados
from app.comun.componentes.graficos import barras
from app.comun.componentes.layout import boton_espera, pagina
from app.comun.db import auditar
from app.comun.componentes.registros import fecha_local
from app.investigacion.identificadores import IDENTIFICADORES

rt = APIRouter()

ESTILO_IMPRESION = Style("""
.hoja { background: #fff; color: #18181b; }
.hoja a { color: #1d4ed8; }
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
.hoja .membrete-logo { height: 4.5rem; width: auto; }
@media print {
  @page { size: A4; margin: 16mm 15mm; }
  .monster-navbar, nav, .no-imprimir, #fh-toast-container, #modal { display: none !important; }
  html, body, main, .uk-container { background: #fff !important; padding: 0 !important; margin: 0 !important;
                                    max-width: none !important; }
  .hoja { box-shadow: none !important; border: 0 !important; padding: 0 !important; }
  .hoja, .hoja * { color: #000 !important; }
  .hoja a { text-decoration: none; }
  .hoja h2, .hoja h3 { break-after: avoid; }
  .hoja .membrete-logo { height: 20mm; }
  /* Tablas anchas: sin recorte del contenedor con desplazamiento; letra y relleno menores. */
  .hoja .overflow-x-auto { overflow: visible !important; }
  .hoja table, .hoja table * { font-size: 8pt !important; }
  .hoja th, .hoja td { padding: .25rem .3rem; }
  .hoja th { white-space: normal !important; }
  .hoja .membrete { border-color: #a1a1aa !important; }
  .hoja li, .hoja tr, .hoja .grafico { break-inside: avoid; }
}
""")


# --- Piezas comunes ------------------------------------------------------------------------------

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


def membrete():
    """Logos del IIMAT y de la Carrera con los nombres institucionales (primera página)."""
    logo = lambda archivo, alt: fh.Img(src=recursos.url(f"img/membrete/{archivo}"), alt=alt,  # noqa: E731
                                       cls="membrete-logo")
    return Div(logo("iimat.png", f"Logo del {config.NOMBRE_INSTITUTO}"),
               Div(Div(config.UNIVERSIDAD, cls="font-semibold uppercase tracking-wide"),
                   Div(config.FACULTAD),
                   Div(f"{config.NOMBRE_CARRERA} · {config.NOMBRE_INSTITUTO}", cls="font-medium"),
                   cls="text-center text-sm leading-snug"),
               logo("cmat.png", f"Logo de la {config.NOMBRE_CARRERA}"),
               cls="membrete flex items-center justify-between gap-4 pb-3 mb-6 border-b-2 border-zinc-300")


def hoja(*contenido, titulo: str = ""):
    """Hoja imprimible con membrete. Al imprimir, el pie de cada página lleva el título del informe
    y «Página X de Y» (cajas de margen de @page: Chrome y Edge; otros navegadores las omiten). Sin
    `titulo`, usa el del primer H1 del documento."""
    if not titulo:
        h1 = next((c for c in contenido if getattr(c, "tag", None) == "h1"), None)
        titulo = "".join(x for x in h1.children if isinstance(x, str)) if h1 else ""
    pie = P(f"Generado el {datetime.now():%d-%m-%Y %H:%M} · {config.NOMBRE_SISTEMA} · "
            f"{config.NOMBRE_INSTITUTO}", cls="apagado text-xs mt-10 pt-3 border-t border-zinc-200")
    izquierda = _cadena_css(f"{titulo} · " if titulo else "") + f' {_cadena_css(config.NOMBRE_CARRERA + " · " + config.NOMBRE_INSTITUTO)}'
    paginas = Style("@media print { @page { @bottom-left { content: " + izquierda + "; font: 8pt sans-serif; "
                    "color: #52525b; } @bottom-right { content: \"Página \" counter(page) \" de \" counter(pages); "
                    "font: 8pt sans-serif; color: #52525b; } } }")
    return Div(paginas, membrete(), *contenido, pie,
               cls="hoja rounded-lg shadow-lg border border-border p-10 max-w-4xl mx-auto")


def cita(p, destacar_uid=None):
    """Referencia con el nombre del investigador destacado, índices e identificadores."""
    autores = []
    for i, a in enumerate(p["autores"]):
        if i:
            autores.append("; ")
        nombre = f"{a['apellidos']}, {' '.join(n[0] + '.' for n in a['nombres'].split() if n)}"
        autores.append(Strong(nombre) if a["interno"] and a["id"] == destacar_uid else nombre)
    medio = p["medio"] or ""
    if p["volumen"]:
        medio += f", {p['volumen']}" + (f"({p['numero']})" if p["numero"] else "")
    if p["paginas"]:
        medio += f", {p['paginas']}"
    extras = []
    if p["indices"]:
        extras.append(f"[{', '.join(i['nombre'] for i in p['indices'])}]")
    if p["estado_publicacion"] != "publicado":
        extras.append(f"({productos.ESTADOS[p['estado_publicacion']].lower()})")
    ids = []
    if p["doi"]:
        ids.append(A(f"doi:{p['doi']}", href=f"https://doi.org/{p['doi']}"))
    if (arxiv := productos.arxiv_de(p)):  # en una versión publicada, el de su preprint
        ids.append(A(f"arXiv:{arxiv}", href=f"https://arxiv.org/abs/{arxiv}"))
    return Li(*autores, f" ({p['anio']}). ", Span(p["titulo"].rstrip(".") + ". ", cls="italic"),
              medio.lstrip(", ") + ("." if medio else ""), " ", " ".join(extras), " ",
              *[x for par in zip(ids, [" "] * len(ids)) for x in par])


def _cifra(valor, texto, href=None):
    """Cifra destacada; con `href`, enlaza a los registros que la componen."""
    contenido = (Div(str(valor), cls="text-2xl font-bold"), Div(texto, cls="apagado text-xs"))
    if href:
        return A(*contenido, href=href, cls="block border border-zinc-200 rounded p-3 text-center hover:bg-zinc-50",
                 style="color: inherit")
    return Div(*contenido, cls="border border-zinc-200 rounded p-3 text-center")


# --- Índice de informes -----------------------------------------------------------------------------

@rt("/informes")
def get(auth):
    tarjetas = []
    if auth["es_investigador"]:
        tarjetas.append(A(Card(Div(UkIcon("file-user", height=22, width=22, cls="text-primary"),
                                   H3("Mi CV", cls="text-base font-semibold mt-2"),
                                   P("Productos, actividades y proyectos por periodo, listo para imprimir.",
                                     cls=TextPresets.muted_sm))),
                          href="/informes/cv", cls="block hover:shadow-md transition"))
    mios = [p for p in proyectos.de_investigador(auth["id"]) if p["vigente"]] if auth["es_investigador"] else []
    if mios:
        tarjetas.append(Card(Div(UkIcon("folder-kanban", height=22, width=22, cls="text-primary"),
                                 H3("Informes de proyecto", cls="text-base font-semibold mt-2"),
                                 Ul(*[Li(A(p["nombre"], href=f"/proyectos/{p['id']}/informe",
                                           cls="text-primary hover:underline text-sm")) for p in mios],
                                    cls="space-y-1 mt-1"))))
    if permisos.puede(auth, "ver_informes_institucionales", unidades.instituto()):
        tarjetas.append(A(Card(Div(UkIcon("landmark", height=22, width=22, cls="text-primary"),
                                   H3("Memoria del instituto", cls="text-base font-semibold mt-2"),
                                   P("Productos que cuentan (indexados y arbitrados), actividades y "
                                     "proyectos de un año, un periodo octubre–septiembre o un rango de "
                                     "fechas. Descarga en XLSX y CSV.", cls=TextPresets.muted_sm))),
                          href="/informes/memoria", cls="block hover:shadow-md transition"))
        tarjetas.append(A(Card(Div(UkIcon("award", height=22, width=22, cls="text-primary"),
                                   H3("Anexo de I+D+i para la acreditación", cls="text-base font-semibold mt-2"),
                                   P("Evidencia de los últimos 5 años ordenada según los criterios de IAC-CINDA, "
                                     "con resumen por año. Descarga en XLSX.", cls=TextPresets.muted_sm))),
                          href="/informes/acreditacion", cls="block hover:shadow-md transition"))
    if permisos.puede(auth, "ver_carga"):
        tarjetas.append(A(Card(Div(UkIcon("clock", height=22, width=22, cls="text-primary"),
                                   H3("Carga docente", cls="text-base font-semibold mt-2"),
                                   P("Carga contratada y su distribución por persona y categoría en un semestre, "
                                     "con JCE, docencia prevista y asignada, e inscripciones por JCE. Descarga en XLSX.",
                                     cls=TextPresets.muted_sm))),
                          href="/informes/carga-docente", cls="block hover:shadow-md transition"))
    if permisos.puede(auth, "ver_informes_institucionales"):
        tarjetas.append(A(Card(Div(UkIcon("users-round", height=22, width=22, cls="text-primary"),
                                   H3("Cuerpo académico", cls="text-base font-semibold mt-2"),
                                   P("Indicadores por año: vinculados, JCE, doctorado y posgrado, categorías, tramos "
                                     "de edad, carga en investigación y proyectos. Descarga en XLSX.",
                                     cls=TextPresets.muted_sm))),
                          href="/informes/cuerpo-academico", cls="block hover:shadow-md transition"))
        tarjetas.append(A(Card(Div(UkIcon("file-spreadsheet", height=22, width=22, cls="text-primary"),
                                   H3("Guía de Antecedentes IAC-CINDA", cls="text-base font-semibold mt-2"),
                                   P("La planilla oficial para la acreditación del pregrado, llenada con los datos del "
                                     "sistema: plan, cuerpo académico, proyectos, publicaciones y actividades.",
                                     cls=TextPresets.muted_sm))),
                          href="/informes/guia-antecedentes", cls="block hover:shadow-md transition"))
    if permisos.puede(auth, "ver_calidad_datos"):
        tarjetas.append(A(Card(Div(UkIcon("list-checks", height=22, width=22, cls="text-primary"),
                                   H3("Calidad de datos", cls="text-base font-semibold mt-2"),
                                   P("Lo que falta o no cuadra antes de generar la memoria, el anexo o los informes "
                                     "de docencia, con quién lo corrige y un enlace para hacerlo.",
                                     cls=TextPresets.muted_sm))),
                          href="/informes/calidad", cls="block hover:shadow-md transition"))
    return pagina("Informes",
                  Div(fh.H2("Informes", cls="uk-h2"),
                      P("Documentos generados a partir de lo registrado en el sistema.", cls=TextPresets.muted_sm),
                      cls="mb-6 space-y-1"),
                  Div(*tarjetas, cls="grid grid-cols-1 md:grid-cols-3 gap-4"),
                  seccion_programados(auth),
                  usuario=auth, seccion="informes")


def seccion_programados(auth):
    """Los informes que la persona recibe solos (por su rol): próximos envíos y los últimos."""
    suyos = programados.suyos(auth)
    if not suyos:
        return ""
    proximos = [x for x in programados.proximos() if x[0] in suyos]
    ultimos = [x for x in programados.ultimos(10) if x["informe"] in suyos]
    return Card(
        H3("Informes que recibe automáticamente", cls="text-base font-semibold"),
        P("Le llegan como avisos (campana y correo, según su preferencia en «Avisos»), con las cifras clave y "
          "el enlace al informe. Las fechas son fijas; si nadie usa el sistema ese día, salen en el siguiente "
          "acceso.", cls=TextPresets.muted_sm),
        Div(Div(Strong("Próximos", cls="text-sm"),
                Ul(*[Li(Span(f"{d:%d-%m-%Y}", cls="font-mono text-sm mr-2"),
                        Span(f"{programados.NOMBRES[i]} ({detalle})", cls="text-sm")) for i, d, detalle in proximos],
                   cls="space-y-1 mt-1")),
            Div(Strong("Últimos envíos", cls="text-sm"),
                Ul(*[Li(Span(fecha_local(x["enviado_en"])[:10], cls="font-mono text-sm mr-2"),
                        Span(f"{programados.NOMBRES[x['informe']]} ({x['ocasion']})", cls="text-sm"),
                        Span(" · sin novedades" if not x["destinatarios"] else "", cls=TextPresets.muted_sm))
                     for x in ultimos], cls="space-y-1 mt-1") if ultimos
                else P("Todavía ninguno.", cls=(TextPresets.muted_sm, "mt-1"))),
            cls="grid grid-cols-1 md:grid-cols-2 gap-6 mt-3"),
        cls="mt-8")


# --- CV ----------------------------------------------------------------------------------------------------

def documento_cv(datos, uid, desde, hasta):
    p = datos["perfil"]
    ids = [f"{IDENTIFICADORES[c][0].split(' (')[0]}: {p[c]}" for c in IDENTIFICADORES if p.get(c)
           and c not in ("scholar_url", "pagina_web")]
    secciones = []
    for clave, titulo in informes.CATEGORIAS:
        lista = datos["grupos"][clave]
        if lista:
            secciones += [H2(f"{titulo} ({len(lista)})"), Ol(*[cita(x, uid) for x in lista], cls="citas")]
    if datos["actividades"]:
        secciones.append(H2(f"Actividades ({datos['n_actividades']})"))
        for tipo, lista in datos["actividades"].items():
            secciones += [H3(tipo), Ul(*[Li(Span(actividades.fechas_texto(a), cls="apagado"), " — ", a["titulo"],
                                            ", " + ", ".join(x for x in (a["institucion"], a["lugar"], a["pais"]) if x)
                                            if (a["institucion"] or a["lugar"] or a["pais"]) else "",
                                            Span(f" ({actividades.ROLES[a['mi_rol']].lower()})", cls="apagado"))
                                         for a in lista], cls="space-y-1")]
    if datos["proyectos"]:
        secciones += [H2("Proyectos"), Ul(*[Li(Strong(x["codigo"] + " — ") if x["codigo"] else "", x["nombre"],
                                               Span(f" ({proyectos.ROLES[x['mi_rol']].lower()}"
                                                    + (f", {x['fecha_inicio'][:4]}–{(x['fecha_fin'] or '')[:4]}"
                                                       if x["fecha_inicio"] else "") + ")", cls="apagado"))
                                            for x in datos["proyectos"]], cls="space-y-1")]
    if not secciones:
        secciones.append(P("No hay registros en el periodo seleccionado.", cls="apagado mt-6"))
    return hoja(
        H1(f"{p['nombres']} {p['apellidos']}"),
        P(" · ".join(x for x in (p["grado"], p["cargo"], p["unidad"]) if x), cls="apagado"),
        P(p["email"], " · ".join([""] + ids) if ids else "", cls="apagado text-sm"),
        P(Strong("Áreas (MSC2020): "), "; ".join(f"{a['codigo']} {a['texto']}" for a in datos["areas"]),
          cls="text-sm mt-2") if datos["areas"] else "",
        P(f"Periodo {desde}–{hasta} · {datos['n_productos']} productos ({datos['n_informe']} cuentan para "
          f"el informe del instituto) · {datos['n_actividades']} actividades", cls="apagado text-sm mt-2"),
        P(p["bio"], cls="mt-4 text-sm whitespace-pre-line") if p["bio"] else "",
        *secciones)


@rt("/informes/cv")
def get(auth, desde: str = "", hasta: str = "", informe: bool = False, uid: int = None,
        filiacion: bool = False):
    uid = uid if (uid and permisos.puede(auth, "ver_cv_ajeno")) else auth["id"]
    d, h = informes.periodo_valido(desde, hasta)
    datos = informes.cv(uid, d, h, informe, filiacion)
    if not datos["perfil"]:
        return Response("Esa cuenta no tiene perfil de investigador.", status_code=404)
    anios = list(range(date.today().year + 1, 1969, -1))
    filtros = [_selector_anio("desde", d, anios, "Desde"), _selector_anio("hasta", h, anios, "Hasta"),
               fh.Label(fh.Input(type="checkbox", name="informe", value="1", checked=informe, cls="uk-checkbox"),
                        Span("Solo lo que cuenta para el informe", cls="text-sm"), cls="flex items-center gap-2"),
               fh.Label(fh.Input(type="checkbox", name="filiacion", value="1", checked=filiacion, cls="uk-checkbox"),
                        Span("Solo con filiación IIMAT/UMSA", cls="text-sm"), cls="flex items-center gap-2"),
               fh.Input(type="hidden", name="uid", value=str(uid)) if uid != auth["id"] else ""]
    consulta = (f"desde={d}&hasta={h}" + ("&informe=1" if informe else "") + ("&filiacion=1" if filiacion else "")
                + (f"&uid={uid}" if uid != auth["id"] else ""))
    return pagina(f"CV · {datos['perfil']['nombres']} {datos['perfil']['apellidos']}",
                  ESTILO_IMPRESION, barra(filtros, [descarga("BibTeX", f"/informes/cv/bibtex?{consulta}")]),
                  documento_cv(datos, uid, d, h),
                  usuario=auth, seccion="informes")


# --- Informe de proyecto -------------------------------------------------------------------------------------

def documento_proyecto(datos, desde, hasta):
    p = datos["proyecto"]
    resp = ", ".join(f"{r['nombres']} {r['apellidos']}" for r in datos["participantes"]
                     if r["rol"] == "responsable" and r["vigente"])
    equipo = Table(Thead(Tr(Th("Nombre"), Th("Rol"), Th("Institución / unidad"), Th("Periodo"))),
                   Tbody(*[Tr(Td(f"{x['nombres']} {x['apellidos']}"), Td(proyectos.ROLES[x["rol"]]),
                              Td(x["afiliacion"] or ("Instituto" if x["interno"] else "")),
                              Td(f"{x['fecha_desde'] or ''} – {x['fecha_hasta'] or 'vigente'}"))
                           for x in datos["participantes"]]))
    acts = Table(Thead(Tr(Th("Fecha"), Th("Actividad"), Th("Lugar"), Th("Responsable"))),
                 Tbody(*[Tr(Td(actividades.fechas_texto(a)), Td(a["titulo"], Span(f" · {a['tipo']}", cls="apagado")),
                            Td(", ".join(x for x in (a["institucion"], a["lugar"], a["pais"]) if x)),
                            Td(f"{a['responsable']['nombres']} {a['responsable']['apellidos']}"
                               if a["responsable"] else "—"))
                         for a in datos["actividades"]])) if datos["actividades"] \
        else P("Sin actividades aprobadas en el periodo.", cls="apagado")
    plan = [Div(H3(f"Periodo {x['periodo']}–{x['periodo'] + 1}: {x['realizadas']} de {len(x['previstas'])} "
                   "actividades previstas realizadas"),
                Table(Thead(Tr(Th("Mes"), Th("Actividad prevista"), Th("Estado"), Th("Actividad registrada"))),
                      Tbody(*[Tr(Td(institucionales.mes_texto(f["mes_previsto"])), Td(f["descripcion"]),
                                 Td({"realizada": "Realizada", "pendiente": "Pendiente", "atrasada": "Atrasada"}[f["estado"]]),
                                 Td(f["realizada_titulo"] or "—")) for f in x["previstas"]])))
            for x in datos["plan"]]
    return hoja(
        P(f"Informe de avance · {desde}–{hasta}", cls="apagado text-sm uppercase tracking-wide"),
        H1(p["nombre"]),
        P(" · ".join(x for x in (f"Proyecto {proyectos.tipo_texto(p).lower()}", p["codigo"], p["fuente_financiamiento"],
                                 f"{p['fecha_inicio'] or '…'} a {p['fecha_fin'] or '…'}") if x), cls="apagado"),
        P(Strong("Responsable: "), resp, cls="text-sm mt-1") if resp else "",
        Div(_cifra(len(datos["productos_informe"]), "productos que cuentan"),
            _cifra(datos["n_cumplen"], "con filiación y agradecimiento"),
            _cifra(len(datos["productos_otros"]), "otros productos"),
            _cifra(len(datos["actividades"]), "actividades"),
            _cifra(sum(x["vigente"] for x in datos["participantes"]), "participantes vigentes"),
            cls="grid grid-cols-5 gap-3 mt-6"),
        *([H2("Objetivo general"), P(p["objetivo_general"])] if p["objetivo_general"] else []),
        *([H2("Objetivos específicos"), Ol(*[Li(o["texto"]) for o in datos["objetivos"]], cls="citas")]
          if datos["objetivos"] else []),
        H2("Equipo"), equipo,
        H2(f"Productos que cuentan para el informe ({len(datos['productos_informe'])})"),
        P("Los fondos exigen que cada publicación lleve la filiación del instituto (IIMAT/UMSA) y agradezca "
          f"al proyecto: {datos['n_cumplen']} de {len(datos['productos_informe'])} lo cumplen.",
          cls="apagado text-sm") if datos["productos_informe"] else "",
        Ol(*[cita(x)(Span(" — " + ("filiación y agradecimiento ✓" if not x["requisitos_faltan"]
                                       else "falta: " + ", ".join(x["requisitos_faltan"])),
                             cls="apagado" if not x["requisitos_faltan"] else "text-amber-700"))
             for x in datos["productos_informe"]], cls="citas") if datos["productos_informe"]
        else P("Ninguno en el periodo.", cls="apagado"),
        *([H2(f"Otros productos ({len(datos['productos_otros'])})"),
           Ol(*[cita(x) for x in datos["productos_otros"]], cls="citas")] if datos["productos_otros"] else []),
        H2(f"Actividades ({len(datos['actividades'])})"), acts,
        *([H2("Plan de actividades: previstas y realizadas"), *plan] if plan else []))


def _proyecto_visible(pid, auth):
    p = proyectos.obtener(pid)
    return p if p and proyectos.puede_ver(pid, auth) else None


def _periodo_proyecto(p, desde, hasta):
    """Por omisión, desde el inicio del proyecto hasta el año actual."""
    actual = date.today().year
    d = desde if str(desde).isdigit() else (p["fecha_inicio"] or str(actual))[:4]
    h = hasta if str(hasta).isdigit() else str(min(actual, int((p["fecha_fin"] or str(actual))[:4])))
    return informes.periodo_valido(d, h)


@rt("/proyectos/{pid}/informe")
def get(auth, pid: int, desde: str = "", hasta: str = ""):
    p = _proyecto_visible(pid, auth)
    if not p:
        return pagina("No encontrado", P("El proyecto no existe o no participa en él."), usuario=auth)
    d, h = _periodo_proyecto(p, desde, hasta)
    anios = list(range(date.today().year + 1, 1999, -1))
    filtros = [_selector_anio("desde", d, anios, "Desde"), _selector_anio("hasta", h, anios, "Hasta")]
    descargas = [descarga("XLSX", f"/proyectos/{pid}/informe/xlsx?desde={d}&hasta={h}")]
    return pagina(f"Informe · {p['nombre']}", ESTILO_IMPRESION,
                  A(UkIcon("arrow-left", height=14, width=14), "Volver al proyecto", href=f"/proyectos/{pid}",
                    cls="no-imprimir inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  barra(filtros, descargas), documento_proyecto(informes.informe_proyecto(pid, d, h), d, h),
                  usuario=auth, seccion="proyectos")


@rt("/proyectos/{pid}/informe/xlsx")
def get(auth, pid: int, desde: str = "", hasta: str = ""):
    p = _proyecto_visible(pid, auth)
    if not p:
        return Response("No encontrado", status_code=404)
    d, h = _periodo_proyecto(p, desde, hasta)
    datos = informes.informe_proyecto(pid, d, h)
    todos = datos["productos_informe"] + datos["productos_otros"]
    marca = {1: "Sí", 0: "No", None: "Sin declarar"}
    filas = [{**f, "Filiación IIMAT/UMSA": marca[x["filiacion_estado"]], "Agradece al proyecto": marca[x["agradece"]]}
             for f, x in zip(informes.filas_productos(todos), todos)]
    hojas = {"Productos": filas,
             "Actividades": informes.filas_actividades(datos["actividades"])}
    if datos["plan"]:
        hojas["Plan"] = [{"Periodo": f"{x['periodo']}–{x['periodo'] + 1}", "Mes": institucionales.mes_texto(f["mes_previsto"]),
                          "Actividad prevista": f["descripcion"], "Estado": f["estado"].capitalize(),
                          "Actividad registrada": f["realizada_titulo"] or ""}
                         for x in datos["plan"] for f in x["previstas"]]
    contenido = informes.a_xlsx(hojas)
    return _archivo(contenido, f"informe-proyecto-{pid}-{d}-{h}.xlsx", XLSX)


# --- Memoria anual -----------------------------------------------------------------------------------------------

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _archivo(contenido: bytes, nombre: str, tipo: str):
    return Response(contenido, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"',
                             "Cache-Control": "private, no-store"})


def _tabla_conteo(titulo_col, datos: dict, etiquetas=None):
    return Table(Thead(Tr(Th(titulo_col), Th("Cantidad", cls="text-right"))),
                 Tbody(*[Tr(Td((etiquetas or {}).get(k, k)), Td(str(v), cls="text-right")) for k, v in datos.items()]))


def seccion_revistas(rv):
    """Artículos que cuentan según su revista: ámbito, acceso abierto, cuartiles y origen del dato."""
    if not rv["articulos"]:
        return ""
    return Div(
        H2("Revistas de los artículos"),
        Div(_cifra(rv["por_ambito"].get("Nacional", 0), "en revistas nacionales"),
            _cifra(rv["por_ambito"].get("Internacional", 0), "en revistas internacionales"),
            _cifra(rv["acceso_abierto"], "en acceso abierto"),
            _cifra(rv["catalogo"], "clasificados por el catálogo"),
            _cifra(rv["declarados"], "con clasificación declarada"), cls="grid grid-cols-5 gap-3 mt-2"),
        Div(Div(H3("Por ámbito de la revista"), _tabla_conteo("Ámbito", rv["por_ambito"])),
            Div(H3("Por cuartil (mejor cuartil del año)"),
                _tabla_conteo("Cuartil", rv["por_cuartil"]) if rv["por_cuartil"]
                else P("Sin cuartiles registrados en el catálogo.", cls="apagado")),
            cls="grid grid-cols-2 gap-6"),
        P(f"{rv['declarados']} artículo(s) en revistas aún no verificadas en el catálogo: su clasificación es la "
          "que declararon los autores." + (" Para la acreditación conviene verificarlas." if not rv["exige_verificada"] else ""),
          cls="text-sm text-amber-700") if rv["declarados"] else "")


def seccion_impacto(imp):
    """Citas de los productos que cuentan, según OpenAlex (IAC-CINDA 3.6.1: impacto con métricas)."""
    if not imp["productos"]:
        return ""
    return Div(
        H2("Impacto"),
        Div(_cifra(imp["citas"], "citas (OpenAlex)"), _cifra(f"{imp['con_datos']} de {imp['productos']}",
                                                            "productos con datos de citas"),
            cls="grid grid-cols-2 gap-3 mt-2 max-w-md"),
        P(f"Citas según OpenAlex, actualizadas el {imp['actualizadas']}. Las citas crecen con el tiempo: compárense "
          "productos del mismo año." if imp["actualizadas"] else
          "Aún no hay datos de citas: la administración puede actualizarlos desde OpenAlex.", cls="apagado text-sm"))


def seccion_metodo(m):
    """Cómo se obtuvieron las cifras (IAC-CINDA 3.6.3: datos, métodos y métricas transparentes)."""
    pol = m["revistas"]["politica"]
    return Div(
        H2("Datos y método"),
        Ul(Li(f"Fuente: registros de {config.NOMBRE_SISTEMA}, mantenidos por cada investigador(a) y "
              "revisados por la administración."),
           Li(f"Periodo: del {informes._fecha_corta(m['desde'])} al {informes._fecha_corta(m['hasta'])}. Los productos "
              "se ubican por año y mes de publicación; las actividades, por su fecha de inicio."),
           Li("Cuenta un producto indexado o arbitrado, aceptado o publicado, si al menos un autor estaba vinculado al "
              "instituto en la fecha de publicación y firmó con la filiación del instituto (IIMAT, CMAT, FCPN o UMSA). "
              "Cada producto se cuenta una vez."),
           Li("Indexado: la revista figuraba ese año en " + ", ".join(pol["indexado"]) + ". "
              + (f"Arbitrado: revistas con revisión por pares o que figuran en {', '.join(pol['arbitrado'])}." if pol["arbitrado"]
                 else "Arbitrado: revistas con revisión por pares.")),
           Li("La indexación de cada revista por año se toma del catálogo de revistas, con la fuente consultada y la fecha "
              "de verificación (ver la columna «Fuente de la indexación» del XLSX). "
              + ("Solo cuentan artículos en revistas verificadas." if m["revistas"]["exige_verificada"] else
                 "Durante el piloto, los artículos en revistas aún no verificadas cuentan con la clasificación declarada "
                 "por sus autores.")),
           Li("Citas: las informa OpenAlex (catálogo abierto) para los productos con DOI o registrados desde OpenAlex, "
              "en la fecha de actualización indicada."),
           Li("Revista nacional: publicada en " + config.PAIS + ". Categoría del investigador: la de su vínculo en la "
              "fecha de cada registro."),
           cls="list-disc pl-5 space-y-1 text-sm"))


def seccion_areas(m):
    """Productos que cuentan por sección MSC2020 de su código principal (PLAN.md §45)."""
    if not m["productos"]:
        return ""
    areas = m["por_area"]
    filas = [Tr(Td(Span(f"{a['seccion']} ", cls="font-mono"), a["texto"]), Td(str(a["indexados"]), cls="text-right"),
                Td(str(a["arbitrados"]), cls="text-right"), Td(str(a["total"]), cls="text-right")) for a in areas]
    if m["sin_area"]:
        filas.append(Tr(Td("Sin clasificar", cls="apagado"), Td(""), Td(""), Td(str(m["sin_area"]), cls="text-right")))
    tabla = Table(Thead(Tr(Th("Sección"), Th("Indexados", cls="text-right"), Th("Arbitrados", cls="text-right"),
                           Th("Total", cls="text-right"))), Tbody(*filas))
    grafico = barras("Productos por sección MSC2020", [a["seccion"] for a in areas[:12]],
                     [("Indexados", [a["indexados"] for a in areas[:12]]),
                      ("Arbitrados", [a["arbitrados"] for a in areas[:12]])],
                     nota="Las 12 secciones con más productos." if len(areas) > 12 else "") if areas else ""
    return Div(
        H2("Por área (MSC2020)"),
        P("Cada producto se cuenta una vez, en la sección de su código MSC2020 principal.", cls="apagado text-sm"),
        Div(Div(tabla), grafico, cls="grid grid-cols-2 gap-6 items-start"),
        P(f"{m['sin_area']} producto(s) sin clasificación MSC2020: complétela en cada producto (Calidad de datos "
          "los lista).", cls="text-sm text-amber-700 no-imprimir") if m["sin_area"] else "")


def seccion_evolucion(serie):
    """Los últimos cinco años en gráficos; cada barra abre la memoria de su año."""
    etiquetas = [x["anio"] for x in serie]
    enlaces = [f"/informes/memoria?anio={y}" for y in etiquetas]

    def g(titulo, *claves_nombres):
        return barras(titulo, etiquetas, [(t, [x[k] for x in serie]) for k, t in claves_nombres],
                      [enlaces] * len(claves_nombres))
    return Div(H2(f"Evolución {etiquetas[0]}–{etiquetas[-1]}"),
               P("Años calendario, con las mismas reglas de esta memoria. Cada barra abre la memoria de su año.",
                 cls="apagado text-sm"),
               Div(g("Productos que cuentan", ("indexados", "Indexados"), ("arbitrados", "Arbitrados")),
                   g("Actividades", ("internacionales", "Internacionales"), ("otras", "Locales y nacionales")),
                   g("Proyectos vigentes", ("proyectos", "Proyectos")),
                   cls="grid grid-cols-3 gap-3"))


def documento_memoria(m, serie=None):
    return hoja(
        H1(m["titulo"]),
        P(f"Del {informes._fecha_corta(m['desde'])} al {informes._fecha_corta(m['hasta'])}.", cls="apagado text-sm")
        if "anio" not in m["params"] else "",
        Div(*[P(a, cls="text-sm") for a in m["avisos"]],
            cls="rounded-md border border-amber-300 bg-amber-50 text-amber-900 p-3 mt-3 space-y-1 no-imprimir")
        if m["avisos"] else "",
        P("Productos que cuentan: indexados o arbitrados, aceptados o publicados en el periodo, con al menos "
          "un autor vinculado (Carrera e Instituto) en la fecha de publicación (con la categoría de ese momento) que firmó "
          "con la filiación del instituto. "
          "Cada producto se cuenta una vez. La producción de investigadores externos figura solo si está "
          "ligada a un proyecto institucional.", cls="apagado text-sm"),
        Div(_cifra(m["n_indexados"], "indexados"), _cifra(m["n_arbitrados"], "arbitrados"),
            _cifra(len(m["actividades"]), "actividades"),
            _cifra(m["por_ambito"].get("internacional", 0), "actividades internacionales"),
            _cifra(len(m["proyectos"]), "proyectos vigentes"), cls="grid grid-cols-5 gap-3 mt-6"),
        seccion_evolucion(serie) if serie else "",
        Div(Div(H3("Productos indexados por índice"),
                _tabla_conteo("Índice", m["por_indice"]) if m["por_indice"] else P("—", cls="apagado")),
            Div(H3("Actividades por tipo"),
                _tabla_conteo("Tipo", m["por_tipo_actividad"]) if m["por_tipo_actividad"] else P("—", cls="apagado")),
            cls="grid grid-cols-2 gap-6"),
        seccion_areas(m),
        seccion_revistas(m["revistas"]),
        seccion_impacto(m["impacto"]),
        H2("Por categoría"),
        P("Cada producto o actividad se cuenta una vez por categoría, aunque participen varias personas "
          "de ella.", cls="apagado text-sm"),
        Table(Thead(Tr(Th("Categoría"), Th("Investigadores", cls="text-right"),
                       Th("Productos que cuentan", cls="text-right"), Th("Actividades", cls="text-right"))),
              Tbody(*[Tr(Td(cat), Td(str(x["investigadores"]), cls="text-right"),
                         Td(str(x["productos"]), cls="text-right"), Td(str(x["actividades"]), cls="text-right"))
                      for cat, x in m["por_categoria"].items()])),
        H2("Por investigador"),
        Table(Thead(Tr(Th("Investigador(a)"), Th("Categoría"), Th("Productos que cuentan", cls="text-right"),
                       Th("Actividades", cls="text-right"))),
              Tbody(*[Tr(Td(f"{x['apellidos']}, {x['nombres']}",
                            Span(f" (hasta {x['hasta']})", cls="apagado") if x.get("hasta") else ""),
                         Td(perfiles.categoria_texto(x["categoria"])),
                         Td(str(x["productos"]), cls="text-right"),
                         Td(str(x["actividades"]), cls="text-right")) for x in m["por_investigador"]]),
              data_tabla="memoria-por-investigador"),
        H2(f"Productos ({len(m['productos'])})"),
        Ol(*[cita(x)(Span(" — clasificación declarada (revista sin verificar)", cls="apagado")
                if x["tipo"] == revistas.TIPO_ARTICULO and not x["clasificacion_catalogo"] else "")
             for x in m["productos"]], cls="citas") if m["productos"]
        else P("No hay productos que cuenten en el periodo.", cls="apagado"),
        Div(H2(f"Por confirmar ({len(m['por_confirmar'])})"),
            P("No se cuentan hasta completar el mes de publicación de cada producto.", cls="apagado text-sm"),
            Ol(*[cita(x)(Span(f" — {x['motivo']}", cls="apagado")) for x in m["por_confirmar"]], cls="citas"))
        if m["por_confirmar"] else "",
        Div(H2(f"Patentes y traducciones ({len(m['otros_resultados'])})"),
            Ol(*[cita(x)(Span(f" — {x['tipo'].lower()}", cls="apagado")) for x in m["otros_resultados"]],
               cls="citas")) if m["otros_resultados"] else "",
        H2(f"Actividades ({len(m['actividades'])})"),
        Ul(*[Li(Span(actividades.fechas_texto(a), cls="apagado"), " — ", a["titulo"],
                Span(f" · {a['tipo']} · {actividades.AMBITOS[a['ambito']].lower()}", cls="apagado"))
             for a in m["actividades"]], cls="space-y-1") if m["actividades"] else P("—", cls="apagado"),
        H2(f"Proyectos vigentes ({len(m['proyectos'])})"),
        *[Div(H3(f"{titulo} ({len(lista)})"),
              Ul(*[Li(Strong(p["codigo"] + " — ") if p["codigo"] else "", p["nombre"],
                      Span(f" · {p['fuente_financiamiento']}" if p["fuente_financiamiento"] else "", cls="apagado"))
                   for p in lista], cls="space-y-1"))
          for titulo, lista in (
              ("Institucionales de investigación",
               [p for p in m["proyectos"] if p["tipo"] == "institucional" and p.get("clase") != "interaccion_social"]),
              ("Institucionales de interacción social",
               [p for p in m["proyectos"] if p["tipo"] == "institucional" and p.get("clase") == "interaccion_social"]),
              ("Individuales", [p for p in m["proyectos"] if p["tipo"] == "individual"]))
          if lista] or [P("—", cls="apagado")],
        seccion_metodo(m))


def _anio(anio):
    return int(anio) if str(anio).isdigit() else date.today().year


def _periodo_memoria(anio="", periodo="", desde="", hasta="", modo=""):
    """Parámetros de la URL → argumentos de informes.memoria. `modo` (anio | periodo | rango) viene
    del formulario; en los enlaces de descarga se deduce de los parámetros presentes."""
    modo = modo or ("periodo" if periodo else "rango" if desde and hasta else "anio")
    if modo == "periodo" and str(periodo).isdigit():
        return {"periodo": int(periodo)}
    if modo == "rango":
        try:
            d, h = date.fromisoformat(desde), date.fromisoformat(hasta)
            if d <= h:
                return {"desde": d.isoformat(), "hasta": h.isoformat()}
        except ValueError:
            pass
    return {"anio": _anio(anio)}


def selector_periodo(r, anios):
    """Año calendario, periodo oct–sep o rango libre (solo se muestran los campos del modo elegido)."""
    modo = "periodo" if "periodo" in r["params"] else "rango" if "desde" in r["params"] else "anio"
    periodos = sorted({a - 1 for a in anios} | set(anios), reverse=True)
    # Clase «hidden» y no el atributo: la clase «flex» anularía el atributo hidden.
    grupo = lambda m, *c: Div(*c, data_modo=m, cls="flex items-center gap-2" + (" hidden" if modo != m else ""))  # noqa: E731
    return [
        Select(*[Option(t, value=v, selected=v == modo) for v, t in
                 (("anio", "Año calendario"), ("periodo", "Periodo oct–sep"), ("rango", "Rango de fechas"))],
               name="modo", cls="uk-select w-44", aria_label="Tipo de periodo",
               data_mostrar_modo=True),
        grupo("anio", Select(*[Option(str(a), value=str(a), selected=r["params"].get("anio") == a) for a in anios],
                             name="anio", cls="uk-select w-28", aria_label="Año")),
        grupo("periodo", Select(*[Option(f"{a}–{a + 1}", value=str(a), selected=r["params"].get("periodo") == a)
                                  for a in periodos], name="periodo", cls="uk-select w-32", aria_label="Periodo")),
        grupo("rango", fh.Input(type="date", name="desde", value=r["desde"], cls="uk-input w-40", aria_label="Desde"),
              Span("a", cls="text-sm"),
              fh.Input(type="date", name="hasta", value=r["hasta"], cls="uk-input w-40", aria_label="Hasta")),
    ]


@rt("/informes/memoria")
def get(auth, anio: str = "", periodo: str = "", desde: str = "", hasta: str = "", modo: str = ""):
    if not permisos.puede(auth, "ver_informes_institucionales", unidades.instituto()):
        return Response("No autorizado", status_code=403)
    m = informes.memoria(**_periodo_memoria(anio, periodo, desde, hasta, modo))
    anios = sorted(set(informes.anios_con_datos()) | {date.today().year}, reverse=True)
    serie = informes.serie_anual(int(m["hasta"][:4]))
    q = urlencode(m["params"])
    descargas = [boton_espera(UkIcon("refresh-cw", height=14, width=14), "Actualizar citas", type="button",
                              cls=(ButtonT.default, ButtonT.sm), hx_post="/informes/citas/actualizar",
                        hx_confirm="¿Consultar en OpenAlex las citas de todos los productos con DOI?",
                        title="Consulta OpenAlex (puede tardar unos segundos)"),
                 descarga("XLSX", f"/informes/memoria/xlsx?{q}"),
                 descarga("CSV productos", f"/informes/memoria/csv/productos?{q}"),
                 descarga("CSV actividades", f"/informes/memoria/csv/actividades?{q}")]
    return pagina(m["titulo"], ESTILO_IMPRESION, barra(selector_periodo(m, anios), descargas),
                  documento_memoria(m, serie), usuario=auth, seccion="informes")


@rt("/informes/citas/actualizar")
def post(auth, sess, req):
    if not permisos.puede(auth, "actualizar_citas"):
        return Response("No autorizado", status_code=403)
    try:
        consultados, actualizados = cosecha.actualizar_citas()
    except importacion.ErrorImportacion as e:
        add_toast(sess, str(e), "error")
    else:
        auditar(auth["id"], "actualizar_citas", "producto", None, f"{actualizados} de {consultados}")
        add_toast(sess, f"Citas actualizadas en {actualizados} de {consultados} producto(s) con DOI.", "success")
    return HtmxResponseHeaders(refresh="true")


@rt("/informes/memoria/xlsx")
def get(auth, anio: str = "", periodo: str = "", desde: str = "", hasta: str = ""):
    if not permisos.puede(auth, "ver_informes_institucionales", unidades.instituto()):
        return Response("No autorizado", status_code=403)
    m = informes.memoria(**_periodo_memoria(anio, periodo, desde, hasta))
    hojas = {
        "Productos": informes.filas_productos(m["productos"]),
        "Actividades": informes.filas_actividades(m["actividades"]),
        "Proyectos": informes.filas_proyectos(m["proyectos"]),
        "Por categoría": [{"Categoría": cat, "Investigadores": x["investigadores"],
                           "Productos que cuentan": x["productos"], "Actividades": x["actividades"]}
                          for cat, x in m["por_categoria"].items()],
        "Por investigador": [{"Investigador(a)": f"{x['apellidos']}, {x['nombres']}",
                              "Categoría": perfiles.categoria_texto(x["categoria"]),
                              "Productos que cuentan": x["productos"], "Actividades": x["actividades"]}
                             for x in m["por_investigador"]],
    }
    if m["por_confirmar"]:
        hojas["Por confirmar"] = informes.filas_productos(m["por_confirmar"])
    if m["otros_resultados"]:
        hojas["Patentes y traducciones"] = informes.filas_productos(m["otros_resultados"])
    return _archivo(informes.a_xlsx(hojas), f"{m['nombre']}.xlsx", XLSX)


@rt("/informes/memoria/csv/{hoja}")
def get(auth, hoja: str, anio: str = "", periodo: str = "", desde: str = "", hasta: str = ""):
    if not permisos.puede(auth, "ver_informes_institucionales", unidades.instituto()):
        return Response("No autorizado", status_code=403)
    m = informes.memoria(**_periodo_memoria(anio, periodo, desde, hasta))
    filas = {"productos": lambda: informes.filas_productos(m["productos"]),
             "actividades": lambda: informes.filas_actividades(m["actividades"]),
             "proyectos": lambda: informes.filas_proyectos(m["proyectos"])}.get(hoja)
    if not filas:
        return Response(status_code=404)
    return _archivo(informes.a_csv(filas()), f"{m['nombre']}-{hoja}.csv", "text/csv; charset=utf-8")
