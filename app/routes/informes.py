"""Informes: CV del investigador, informe de proyecto y memoria anual del instituto.

Los informes son páginas pensadas para imprimir: en pantalla se ven como una hoja, y el botón
«Imprimir / Guardar PDF» usa el diálogo del navegador (así las fórmulas LaTeX salen con KaTeX,
cosa que un generador de PDF en el servidor no haría). La memoria y el informe de proyecto se
descargan además en XLSX y CSV.
"""
from datetime import date, datetime

from urllib.parse import urlencode

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, H1, H2, H3, Li, Ol, Option, P, Response, Select,
                             Span, Strong, Style, Table, Tbody, Td, Th, Thead, Tr, Ul)
from monsterui.all import Button, ButtonT, Card, TextPresets, UkIcon

from app import actividades, config, informes, institucionales, perfiles, productos, proyectos
from app.components.layout import pagina
from app.identificadores import IDENTIFICADORES

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
@media print {
  @page { size: A4; margin: 16mm 15mm; }
  .monster-navbar, nav, .no-imprimir, #fh-toast-container, #modal { display: none !important; }
  html, body, main, .uk-container { background: #fff !important; padding: 0 !important; margin: 0 !important;
                                    max-width: none !important; }
  .hoja { box-shadow: none !important; border: 0 !important; padding: 0 !important; }
  .hoja, .hoja * { color: #000 !important; }
  .hoja a { text-decoration: none; }
  .hoja h2, .hoja h3 { break-after: avoid; }
  .hoja li, .hoja tr { break-inside: avoid; }
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
        Div(*descargas,
            Button(UkIcon("printer", height=16, width=16), "Imprimir / Guardar PDF", type="button",
                   cls=ButtonT.primary, onclick="window.print()"),
            cls="flex flex-wrap gap-2"),
        cls="no-imprimir flex flex-wrap items-center justify-between gap-4 mb-6")


def descarga(texto, href):
    return A(UkIcon("download", height=14, width=14), texto, href=href,
             cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1")


def hoja(*contenido):
    pie = P(f"Generado el {datetime.now():%d-%m-%Y %H:%M} · Portal de Investigación · "
            f"{config.NOMBRE_INSTITUTO}", cls="apagado text-xs mt-10 pt-3 border-t border-zinc-200")
    return Div(*contenido, pie, cls="hoja rounded-lg shadow-lg border border-border p-10 max-w-4xl mx-auto")


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
    if p["arxiv_id"]:
        ids.append(A(f"arXiv:{p['arxiv_id']}", href=f"https://arxiv.org/abs/{p['arxiv_id']}"))
    return Li(*autores, f" ({p['anio']}). ", Span(p["titulo"].rstrip(".") + ". ", cls="italic"),
              medio.lstrip(", ") + ("." if medio else ""), " ", " ".join(extras), " ",
              *[x for par in zip(ids, [" "] * len(ids)) for x in par])


def _cifra(valor, texto):
    return Div(Div(str(valor), cls="text-2xl font-bold"), Div(texto, cls="apagado text-xs"),
               cls="border border-zinc-200 rounded p-3 text-center")


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
    if auth["es_admin"]:
        tarjetas.append(A(Card(Div(UkIcon("landmark", height=22, width=22, cls="text-primary"),
                                   H3("Memoria del instituto", cls="text-base font-semibold mt-2"),
                                   P("Productos que cuentan (indexados y arbitrados), actividades y "
                                     "proyectos de un año, un periodo octubre–septiembre o un rango de "
                                     "fechas. Descarga en XLSX y CSV.", cls=TextPresets.muted_sm))),
                          href="/informes/memoria", cls="block hover:shadow-md transition"))
    return pagina("Informes",
                  Div(fh.H2("Informes", cls="uk-h2"),
                      P("Documentos generados a partir de lo registrado en el portal.", cls=TextPresets.muted_sm),
                      cls="mb-6 space-y-1"),
                  Div(*tarjetas, cls="grid grid-cols-1 md:grid-cols-3 gap-4"),
                  usuario=auth, seccion="informes")


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
def get(auth, desde: str = "", hasta: str = "", informe: bool = False, uid: int = None):
    uid = uid if (uid and auth["es_admin"]) else auth["id"]
    d, h = informes.periodo_valido(desde, hasta)
    datos = informes.cv(uid, d, h, informe)
    if not datos["perfil"]:
        return Response("Esa cuenta no tiene perfil de investigador.", status_code=404)
    anios = list(range(date.today().year + 1, 1969, -1))
    filtros = [_selector_anio("desde", d, anios, "Desde"), _selector_anio("hasta", h, anios, "Hasta"),
               fh.Label(fh.Input(type="checkbox", name="informe", value="1", checked=informe, cls="uk-checkbox"),
                        Span("Solo lo que cuenta para el informe", cls="text-sm"), cls="flex items-center gap-2"),
               fh.Input(type="hidden", name="uid", value=str(uid)) if uid != auth["id"] else ""]
    consulta = f"desde={d}&hasta={h}" + ("&informe=1" if informe else "") + (f"&uid={uid}" if uid != auth["id"] else "")
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
        P(" · ".join(x for x in (f"Proyecto {proyectos.TIPOS[p['tipo']].lower()}", p["codigo"], p["fuente_financiamiento"],
                                 f"{p['fecha_inicio'] or '…'} a {p['fecha_fin'] or '…'}") if x), cls="apagado"),
        P(Strong("Responsable: "), resp, cls="text-sm mt-1") if resp else "",
        Div(_cifra(len(datos["productos_informe"]), "productos que cuentan"),
            _cifra(len(datos["productos_otros"]), "otros productos"),
            _cifra(len(datos["actividades"]), "actividades"),
            _cifra(sum(x["vigente"] for x in datos["participantes"]), "participantes vigentes"),
            cls="grid grid-cols-4 gap-3 mt-6"),
        *([H2("Objetivo general"), P(p["objetivo_general"])] if p["objetivo_general"] else []),
        *([H2("Objetivos específicos"), Ol(*[Li(o["texto"]) for o in datos["objetivos"]], cls="citas")]
          if datos["objetivos"] else []),
        H2("Equipo"), equipo,
        H2(f"Productos que cuentan para el informe ({len(datos['productos_informe'])})"),
        Ol(*[cita(x) for x in datos["productos_informe"]], cls="citas") if datos["productos_informe"]
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
    hojas = {"Productos": informes.filas_productos(datos["productos_informe"] + datos["productos_otros"]),
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


def documento_memoria(m):
    return hoja(
        P(config.NOMBRE_INSTITUTO, cls="apagado text-sm uppercase tracking-wide"),
        H1(m["titulo"]),
        P(f"Del {informes._fecha_corta(m['desde'])} al {informes._fecha_corta(m['hasta'])}.", cls="apagado text-sm")
        if "anio" not in m["params"] else "",
        Div(*[P(a, cls="text-sm") for a in m["avisos"]],
            cls="rounded-md border border-amber-300 bg-amber-50 text-amber-900 p-3 mt-3 space-y-1 no-imprimir")
        if m["avisos"] else "",
        P("Productos que cuentan: indexados o arbitrados, aceptados o publicados en el periodo, con al menos "
          "un autor vinculado al instituto en la fecha de publicación (con la categoría de ese momento). "
          "Cada producto se cuenta una vez. La producción de investigadores externos figura solo si está "
          "ligada a un proyecto institucional.", cls="apagado text-sm"),
        Div(_cifra(m["n_indexados"], "indexados"), _cifra(m["n_arbitrados"], "arbitrados"),
            _cifra(len(m["actividades"]), "actividades"),
            _cifra(m["por_ambito"].get("internacional", 0), "internacionales"),
            _cifra(len(m["proyectos"]), "proyectos vigentes"), cls="grid grid-cols-5 gap-3 mt-6"),
        Div(Div(H3("Productos indexados por índice"),
                _tabla_conteo("Índice", m["por_indice"]) if m["por_indice"] else P("—", cls="apagado")),
            Div(H3("Actividades por tipo"),
                _tabla_conteo("Tipo", m["por_tipo_actividad"]) if m["por_tipo_actividad"] else P("—", cls="apagado")),
            cls="grid grid-cols-2 gap-6"),
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
                         Td(str(x["actividades"]), cls="text-right")) for x in m["por_investigador"]])),
        H2(f"Productos ({len(m['productos'])})"),
        Ol(*[cita(x) for x in m["productos"]], cls="citas") if m["productos"]
        else P("No hay productos que cuenten en el periodo.", cls="apagado"),
        Div(H2(f"Por confirmar ({len(m['por_confirmar'])})"),
            P("No se cuentan hasta completar el mes de publicación de cada producto.", cls="apagado text-sm"),
            Ol(*[Li(cita(x), Span(f" — {x['motivo']}", cls="apagado")) for x in m["por_confirmar"]], cls="citas"))
        if m["por_confirmar"] else "",
        H2(f"Actividades ({len(m['actividades'])})"),
        Ul(*[Li(Span(actividades.fechas_texto(a), cls="apagado"), " — ", a["titulo"],
                Span(f" · {a['tipo']} · {actividades.AMBITOS[a['ambito']].lower()}", cls="apagado"))
             for a in m["actividades"]], cls="space-y-1") if m["actividades"] else P("—", cls="apagado"),
        H2(f"Proyectos vigentes ({len(m['proyectos'])})"),
        *[Div(H3(f"{titulo} ({len(lista)})"),
              Ul(*[Li(Strong(p["codigo"] + " — ") if p["codigo"] else "", p["nombre"],
                      Span(f" · {p['fuente_financiamiento']}" if p["fuente_financiamiento"] else "", cls="apagado"))
                   for p in lista], cls="space-y-1"))
          for titulo, lista in (("Institucionales", [p for p in m["proyectos"] if p["tipo"] == "institucional"]),
                                ("Individuales", [p for p in m["proyectos"] if p["tipo"] == "individual"]))
          if lista] or [P("—", cls="apagado")])


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
               onchange="this.form.querySelectorAll('[data-modo]').forEach(e => e.classList.toggle('hidden', e.dataset.modo != this.value))"),
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
    if not auth["es_admin"]:
        return Response("No autorizado", status_code=403)
    m = informes.memoria(**_periodo_memoria(anio, periodo, desde, hasta, modo))
    anios = sorted(set(informes.anios_con_datos()) | {date.today().year}, reverse=True)
    q = urlencode(m["params"])
    descargas = [descarga("XLSX", f"/informes/memoria/xlsx?{q}"),
                 descarga("CSV productos", f"/informes/memoria/csv/productos?{q}"),
                 descarga("CSV actividades", f"/informes/memoria/csv/actividades?{q}")]
    return pagina(m["titulo"], ESTILO_IMPRESION, barra(selector_periodo(m, anios), descargas),
                  documento_memoria(m), usuario=auth, seccion="informes")


@rt("/informes/memoria/xlsx")
def get(auth, anio: str = "", periodo: str = "", desde: str = "", hasta: str = ""):
    if not auth["es_admin"]:
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
        hojas["Sin mes (por confirmar)"] = informes.filas_productos(m["por_confirmar"])
    return _archivo(informes.a_xlsx(hojas), f"{m['nombre']}.xlsx", XLSX)


@rt("/informes/memoria/csv/{hoja}")
def get(auth, hoja: str, anio: str = "", periodo: str = "", desde: str = "", hasta: str = ""):
    if not auth["es_admin"]:
        return Response("No autorizado", status_code=403)
    m = informes.memoria(**_periodo_memoria(anio, periodo, desde, hasta))
    filas = {"productos": lambda: informes.filas_productos(m["productos"]),
             "actividades": lambda: informes.filas_actividades(m["actividades"]),
             "proyectos": lambda: informes.filas_proyectos(m["proyectos"])}.get(hoja)
    if not filas:
        return Response(status_code=404)
    return _archivo(informes.a_csv(filas()), f"{m['nombre']}-{hoja}.csv", "text/csv; charset=utf-8")
