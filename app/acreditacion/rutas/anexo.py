"""Anexo de I+D+i para la acreditación (administración): documento imprimible ordenado por criterio
de IAC-CINDA y su XLSX. Sin extensión en la URL de descarga: la ruta de archivos estáticos
capturaría «….xlsx»."""
from datetime import date
from urllib.parse import urlencode

import fasthtml.common as fh
from fasthtml.common import (APIRouter, Div, H1, H2, H3, Li, Ol, Option, P, Response, Select, Span, Table, Tbody,
                             Td, Th, Thead, Tr, Ul)

from app.acreditacion import anexo as acreditacion, informes
from app.investigacion import actividades, proyectos
from app.comun import config, estudiantes
from app.comun.componentes.layout import pagina
from app.acreditacion.rutas.informes import (ESTILO_IMPRESION, XLSX, _archivo, _cifra, _tabla_conteo, barra, cita,
                                             descarga, hoja, seccion_metodo)

rt = APIRouter()


def _num(n):
    return Td(str(n), cls="text-right tabular-nums")


def _lista_actividades(acts, vacio="Sin registros en el periodo."):
    if not acts:
        return P(vacio, cls="apagado")
    return Ul(*[Li(Span(actividades.fechas_texto(a), cls="apagado"), " — ", a["titulo"],
                   Span(" · " + " · ".join(x for x in (a["tipo"], a["institucion"], a["pais"],
                                                         actividades.AMBITOS[a["ambito"]].lower()) if x),
                        cls="apagado"))
                for a in acts], cls="space-y-1")


def _lista_productos(prods, vacio="Sin registros en el periodo.", detalle=True):
    if not prods:
        return P(vacio, cls="apagado")
    def extra(p):
        d = p.get("detalle_revista")
        if not detalle or not d or not d["revista"]:
            return ""
        return Span(f" — {d['ambito'].lower()}" + (f", {d['cuartil']}" if d["cuartil"] else "")
                    + ("" if p["clasificacion_catalogo"] else ", clasificación declarada"), cls="apagado")
    return Ol(*[cita(p)(extra(p)) for p in prods], cls="citas")


def _criterio(codigo, titulo, que, *contenido):
    """Sección de un criterio: código, título, qué evidencia aporta y el contenido."""
    return Div(H2(Span(codigo, cls="font-mono text-base mr-2"), titulo), P(que, cls="apagado text-sm"), *contenido,
               cls="space-y-2")


def _nombres(personas_):
    return ", ".join(f"{x['nombres']} {x['apellidos']}" for x in personas_)


def seccion_estudiantes(e):
    """2.3.2 · 3.6.1 d · 2.3.4: tesis dirigidas y participación de estudiantes (y graduados)."""
    tesis = Ul(*[Li(Span(f"{t['producto']['anio']} — ", cls="apagado"), t["producto"]["titulo"],
                    Span(f" · {_nombres(t['tesistas']) or 'tesista sin registrar'}"
                         f" ({estudiantes.NIVELES.get(t['nivel'], 'nivel sin registrar').lower()}, {t['estado']})"
                         f" · dirige: {_nombres(t['directores'])}", cls="apagado"))
                 for t in e["tesis"]], cls="space-y-1") if e["tesis"] else P("Sin tesis dirigidas en el periodo.", cls="apagado")
    return _criterio(
        "2.3.2 · 3.6.1 d · 2.3.4", "Estudiantes en la investigación",
        "Tesis dirigidas por investigadores del instituto y participación de estudiantes (y graduados) en publicaciones, "
        "proyectos y actividades, según sus periodos de estudio registrados.",
        Div(_cifra(sum(t["estado"] == "defendida" for t in e["tesis"]), "tesis defendidas"),
            _cifra(sum(t["estado"] == "en curso" for t in e["tesis"]), "tesis en curso"),
            _cifra(len(e["productos"]), "productos con estudiantes"),
            _cifra(len(e["proyectos"]), "proyectos con estudiantes"),
            _cifra(len(e["graduados"]), "productos con graduados"), cls="grid grid-cols-5 gap-3"),
        Div(Table(Thead(Tr(Th("Nivel"), Th("Estado"), Th("Tesis", cls="text-right"))),
                  Tbody(*[Tr(Td(n), Td(est), _num(c)) for (n, est), c in sorted(e["tesis_por_nivel"].items())]))
            if e["tesis_por_nivel"] else ""),
        H3("Tesis dirigidas"), tesis,
        H3("Productos con estudiantes coautores"), _lista_productos(e["productos"], detalle=False),
        H3("Proyectos con estudiantes"),
        Ul(*[Li(p["nombre"], Span(f" · {_nombres(p['estudiantes'])}", cls="apagado")) for p in e["proyectos"]],
           cls="space-y-1") if e["proyectos"] else P("Sin registros en el periodo.", cls="apagado"),
        H3("Actividades con estudiantes"),
        Ul(*[Li(Span(actividades.fechas_texto(a), cls="apagado"), " — ", a["titulo"],
                Span(f" · {_nombres(a['estudiantes'])}", cls="apagado")) for a in e["actividades"]],
           cls="space-y-1") if e["actividades"] else P("Sin registros en el periodo.", cls="apagado"))


def seccion_internacionalizacion(a):
    """3.5.2 c: coautoría internacional (con su cobertura) y proyectos internacionales."""
    c = a["coautoria"]
    faltan = c["con_externos"] - c["con_pais"]
    internacionales = [p for p in a["proyectos"] if p["ambito_efectivo"] == "internacional"]
    sin_ambito = sum(p["ambito_efectivo"] is None for p in a["proyectos"])
    return _criterio(
        "3.5.2 c", "Internacionalización de la investigación",
        "Publicaciones con coautores de instituciones de otros países y proyectos internacionales (con contrapartes "
        "o financiamiento de otros países).",
        Div(_cifra(c["internacionales"], "artículos con coautoría internacional"),
            _cifra(f"{c['con_pais']} de {c['con_externos']}", "artículos con país de todos sus coautores"),
            _cifra(len(internacionales), "proyectos internacionales"),
            _cifra(len(a["movilidad_internacional"]), "estancias internacionales"), cls="grid grid-cols-4 gap-3"),
        P(f"Cobertura incompleta: en {faltan} artículo(s) falta el país de algún coautor externo, por lo que la coautoría "
          "internacional puede estar subestimada (complételo en Investigadores → Coautores externos)." if faltan else
          "El país de todos los coautores externos está registrado.", cls="text-sm" + (" text-amber-700" if faltan else "")),
        P(f"{sin_ambito} proyecto(s) sin ámbito indicado ni contrapartes." if sin_ambito else "", cls="text-sm text-amber-700"),
        Div(H3("Países de los coautores"), _tabla_conteo("País", c["por_pais"])) if c["por_pais"] else "",
        Div(H3("Proyectos internacionales"),
            Ul(*[Li(p["nombre"], Span(" · " + "; ".join(f"{x['institucion']} ({x['pais'] or '?'})" for x in p["contrapartes"]),
                                      cls="apagado") if p["contrapartes"] else "") for p in internacionales],
               cls="space-y-1")) if internacionales else "")


def documento(a):
    m = a["memoria"]
    anios = a["anios"]
    cols = [("investigadores", "Investigadores"), ("jce", "JCE"), ("indexados", "Art. indexados"),
            ("arbitrados", "Art. arbitrados"), ("nacionales", "En revistas nacionales"),
            ("internacionales", "En revistas internacionales"), ("libros", "Libros y capítulos"),
            ("tecnicos", "Patentes, software, traducciones"), ("presentaciones", "Presentaciones"),
            ("estancias", "Estancias"), ("transferencia", "Transferencia"), ("redes", "Redes"),
            ("proyectos", "Proyectos vigentes"), ("tesis_defendidas", "Tesis defendidas"),
            ("con_estudiantes", "Productos con estudiantes"), ("coautoria_internacional", "Artículos con coautoría internacional"),
            ("proyectos_internacionales", "Proyectos internacionales"), ("citas", "Citas")]
    resumen = Div(Table(Thead(Tr(Th("Indicador"), *[Th(str(x["anio"]), cls="text-right") for x in anios])),
                        Tbody(*[Tr(Td(t), *[_num(x[k]) for x in anios]) for k, t in cols])),
                  cls="overflow-x-auto")
    categorias = sorted({c for x in a["cuerpo"] for c in x["por_categoria"]})
    cuerpo = Div(Table(Thead(Tr(Th("Categoría (al 31 de diciembre)"), *[Th(str(x["anio"]), cls="text-right") for x in a["cuerpo"]])),
                       Tbody(*[Tr(Td(c), *[_num(x["por_categoria"].get(c, 0)) for x in a["cuerpo"]]) for c in categorias],
                             Tr(Td("Total", cls="font-semibold"), *[_num(x["total"]) for x in a["cuerpo"]]),
                             Tr(Td("Jornada completa equivalente (40 h)"), *[_num(x["jce"]) for x in a["cuerpo"]]),
                             Tr(Td("Sin jornada registrada"), *[_num(x["sin_jornada"]) for x in a["cuerpo"]]))),
                 cls="overflow-x-auto")
    rv = m["revistas"]
    avisos = [*m["avisos"]]
    if m["por_confirmar"]:
        avisos.append(f"{len(m['por_confirmar'])} producto(s) por confirmar no se cuentan (ver la hoja «Por confirmar» del XLSX).")
    if not a["exige_verificada"] and rv["declarados"]:
        avisos.append(f"{rv['declarados']} artículo(s) cuentan con clasificación declarada (revista sin verificar).")
    return hoja(
        P(f"{config.NOMBRE_INSTITUTO} · {config.UNIVERSIDAD}", cls="apagado text-sm uppercase tracking-wide"),
        H1(f"Anexo de I+D+i para la acreditación, {a['desde_anio']}–{a['hasta_anio']}"),
        P("Evidencia de investigación, desarrollo e innovación ordenada según los criterios de IAC-CINDA para programas "
          "de pregrado (junio 2025). Los datos provienen del Portal de Investigación; el método está al final.",
          cls="apagado text-sm"),
        Div(*[P(x, cls="text-sm") for x in avisos],
            cls="rounded-md border border-amber-300 bg-amber-50 text-amber-900 p-3 mt-3 space-y-1") if avisos else "",
        Div(_cifra(len(a["articulos"]), "artículos que cuentan"), _cifra(len(a["libros"]), "libros y capítulos"),
            _cifra(len(a["presentaciones"]), "presentaciones"), _cifra(len(a["proyectos"]), "proyectos"),
            _cifra(m["impacto"]["citas"], "citas (OpenAlex)"), cls="grid grid-cols-5 gap-3 mt-6"),
        H2("Resumen por año"), resumen,
        _criterio("2.2.1", "Cuerpo académico", "Dotación, categoría y dedicación (jornada) de quienes estuvieron "
                  "vinculados al instituto cada año, según el historial de Recursos Humanos.", cuerpo),
        _criterio("3.6.3 a", "Publicaciones en revistas indexadas y arbitradas",
                  f"{len(a['articulos'])} artículos que cuentan: {rv['por_ambito'].get('Nacional', 0)} en revistas nacionales, "
                  f"{rv['por_ambito'].get('Internacional', 0)} en internacionales, {rv['acceso_abierto']} en acceso abierto.",
                  Div(Div(H3("Por índice"), _tabla_conteo("Índice", m["por_indice"]) if m["por_indice"] else P("—", cls="apagado")),
                      Div(H3("Por cuartil"), _tabla_conteo("Cuartil", rv["por_cuartil"]) if rv["por_cuartil"]
                          else P("Sin cuartiles registrados en el catálogo.", cls="apagado")),
                      cls="grid grid-cols-2 gap-6"),
                  _lista_productos(a["articulos"])),
        _criterio("3.6.3 b", "Libros y capítulos con referato externo", "Libros y capítulos arbitrados que cuentan.",
                  _lista_productos(a["libros"], detalle=False)),
        _criterio("3.6.3 d · e", "Patentes, productos tecnológicos y traducciones",
                  "Patentes (solicitadas o concedidas), software y traducciones de autores vinculados en la fecha.",
                  _lista_productos(a["tecnicos"], detalle=False)),
        _criterio("3.6.3 f · 3.4.1", "Transferencia de conocimiento y divulgación",
                  "Actividades de transferencia a la sociedad, el sector productivo o las políticas públicas, y de divulgación.",
                  H3("Transferencia"), _lista_actividades(a["transferencia"]),
                  H3("Divulgación"), _lista_actividades(a["divulgacion"])),
        _criterio("3.6.3 g · 3.5.2 a", "Estancias y pasantías en centros de investigación",
                  f"{len(a['estancias'])} estancias o visitas; {len(a['movilidad_internacional'])} internacionales.",
                  _lista_actividades(a["estancias"])),
        _criterio("3.6.3 h", "Participación en proyectos de I+D+i",
                  "Proyectos vigentes en el periodo, con su fuente de financiamiento y participantes del instituto.",
                  Div(Table(Thead(Tr(Th("Proyecto"), Th("Tipo"), Th("Ámbito"), Th("Periodo"), Th("Financiamiento"), Th("Responsable"),
                                     Th("Participantes del instituto", cls="text-right"))),
                            Tbody(*[Tr(Td((p["codigo"] + " — " if p["codigo"] else "") + p["nombre"],
                                          Div("Contrapartes: " + "; ".join(f"{c['institucion']} ({c['pais'] or '?'})"
                                                                           for c in p["contrapartes"]), cls="apagado text-xs")
                                          if p["contrapartes"] else ""),
                                       Td(proyectos.TIPOS[p["tipo"]]),
                                       Td(proyectos.AMBITOS.get(p["ambito_efectivo"], "Sin indicar")),
                                       Td(f"{p['fecha_inicio'] or '…'} a {p['fecha_fin'] or '…'}"),
                                       Td(p["fuente_financiamiento"] or "—"), Td(p["responsables"] or "—"), _num(p["n_internos"]))
                                    for p in a["proyectos"]])), cls="overflow-x-auto")
                  if a["proyectos"] else P("Sin proyectos vigentes en el periodo.", cls="apagado")),
        seccion_estudiantes(a["estudiantes"]),
        _criterio("3.6.3 i", "Presentaciones en congresos y eventos científicos",
                  f"{len(a['presentaciones'])} eventos con exposición de integrantes del instituto; "
                  f"{sum(x['ambito'] == 'internacional' for x in a['presentaciones'])} internacionales.",
                  _lista_actividades(a["presentaciones"])),
        _criterio("3.6.3 j", "Participación en redes de investigación", "Redes nacionales e internacionales.",
                  _lista_actividades(a["redes"])),
        _criterio("2.2.1 d", "Reconocimiento de pares", "Participación en comités científicos o editoriales.",
                  _lista_actividades(a["comites"])),
        seccion_internacionalizacion(a),
        _criterio("3.6.1", "Impacto", "Citas según OpenAlex de los productos que cuentan, por año de publicación.",
                  P(f"{m['impacto']['citas']} citas en {m['impacto']['con_datos']} de {m['impacto']['productos']} productos"
                    + (f", actualizadas el {m['impacto']['actualizadas']}." if m["impacto"]["actualizadas"] else "."),
                    cls="text-sm")),
        Div(H2("Aún no registrado en el portal"),
            Ul(Li("Premios y distinciones; arbitraje de artículos (2.2.1 d)."),
               Li("Asesorías y prestación de servicios (3.4.3); impacto de la vinculación (3.4.1)."),
               cls="list-disc pl-5 space-y-1 text-sm"),
            P("Estos criterios deben documentarse por otros medios hasta que el portal los registre.", cls="apagado text-sm")),
        seccion_metodo(m))


def _ventana(desde, hasta):
    d, h = acreditacion.ventana_por_omision()
    d = int(desde) if str(desde).isdigit() else d
    h = int(hasta) if str(hasta).isdigit() else h
    h = min(h, date.today().year)
    return (min(d, h), max(d, h)) if h - d <= 10 else (h - 10, h)


@rt("/informes/acreditacion")
def get(auth, desde: str = "", hasta: str = "", revistas: str = "verificadas"):
    if not auth["es_admin"]:
        return Response("No autorizado", status_code=403)
    d, h = _ventana(desde, hasta)
    estricto = revistas != "todas"
    a = acreditacion.anexo(d, h, estricto)
    anios = list(range(date.today().year, 1999, -1))
    filtros = [fh.Label(Span("Desde", cls="text-sm"), Select(*[Option(str(x), selected=x == d) for x in anios],
                                                             name="desde", cls="uk-select w-28"), cls="flex items-center gap-2"),
               fh.Label(Span("Hasta", cls="text-sm"), Select(*[Option(str(x), selected=x == h) for x in anios],
                                                             name="hasta", cls="uk-select w-28"), cls="flex items-center gap-2"),
               Select(Option("Solo revistas verificadas", value="verificadas", selected=estricto),
                      Option("Incluir revistas sin verificar", value="todas", selected=not estricto),
                      name="revistas", cls="uk-select w-60", aria_label="Revistas")]
    q = urlencode({"desde": d, "hasta": h, "revistas": "verificadas" if estricto else "todas"})
    return pagina(f"Anexo de I+D+i {d}–{h}", ESTILO_IMPRESION,
                  barra(filtros, [descarga("XLSX", f"/informes/acreditacion/xlsx?{q}")]),
                  documento(a), usuario=auth, seccion="informes")


@rt("/informes/acreditacion/xlsx")
def get(auth, desde: str = "", hasta: str = "", revistas: str = "verificadas"):
    if not auth["es_admin"]:
        return Response("No autorizado", status_code=403)
    d, h = _ventana(desde, hasta)
    a = acreditacion.anexo(d, h, revistas != "todas")
    m = a["memoria"]
    nombres = {"investigadores": "Investigadores", "jce": "JCE (40 h)", "indexados": "Artículos indexados",
               "arbitrados": "Artículos arbitrados", "nacionales": "En revistas nacionales",
               "internacionales": "En revistas internacionales", "libros": "Libros y capítulos",
               "tecnicos": "Patentes, software, traducciones", "presentaciones": "Presentaciones", "estancias": "Estancias",
               "transferencia": "Transferencia", "redes": "Redes", "proyectos": "Proyectos vigentes",
               "tesis_defendidas": "Tesis defendidas", "con_estudiantes": "Productos con estudiantes",
               "coautoria_internacional": "Artículos con coautoría internacional",
               "proyectos_internacionales": "Proyectos internacionales", "citas": "Citas"}
    resumen = [{"Indicador": t, **{str(x["anio"]): x[k] for x in a["anios"]}} for k, t in nombres.items()]
    cuerpo = [{"Año": c["anio"], "Investigador(a)": f"{p['apellidos']}, {p['nombres']}", "Categoría": p["categoria"],
               "Jornada (h/semana)": p["jornada"] or ""} for c in a["cuerpo"] for p in c["personas"]]

    def actividades_con(criterio, acts):
        return [{"Criterio": criterio, **f} for f in informes.filas_actividades(acts)]
    acts = (actividades_con("3.6.3 f Transferencia", a["transferencia"]) + actividades_con("3.4.1 Divulgación", a["divulgacion"])
            + actividades_con("3.6.3 g Estancias", a["estancias"]) + actividades_con("3.6.3 i Presentaciones", a["presentaciones"])
            + actividades_con("3.6.3 j Redes", a["redes"]) + actividades_con("2.2.1 d Comités", a["comites"]))
    metodo = [{"Tema": "Periodo", "Descripción": f"{a['desde']} a {a['hasta']}"},
              {"Tema": "Revistas", "Descripción": "Solo revistas verificadas en el catálogo" if a["exige_verificada"]
               else "Incluye revistas sin verificar (clasificación declarada)"},
              {"Tema": "Índices que cuentan como indexado", "Descripción": ", ".join(m["revistas"]["politica"]["indexado"])},
              {"Tema": "Índices que cuentan como arbitrado", "Descripción": ", ".join(m["revistas"]["politica"]["arbitrado"])},
              {"Tema": "Regla de conteo", "Descripción": "Al menos un autor vinculado al instituto en la fecha de publicación "
               "que firmó con la filiación IIMAT/UMSA; cada producto se cuenta una vez."},
              {"Tema": "Cuerpo académico", "Descripción": "Personas con vínculo vigente al 31 de diciembre de cada año; "
               "JCE = horas semanales / 40."},
              {"Tema": "Citas", "Descripción": "OpenAlex, en la fecha de actualización de cada producto."}]
    contenido = informes.a_xlsx({
        "Resumen por año": resumen, "2.2.1 Cuerpo académico": cuerpo,
        "3.6.3 a Publicaciones": informes.filas_productos(a["articulos"]),
        "3.6.3 b Libros y capítulos": informes.filas_productos(a["libros"]),
        "3.6.3 d-e Técnicos": informes.filas_productos(a["tecnicos"]),
        "Actividades por criterio": acts,
        "3.6.3 h Proyectos": informes.filas_proyectos(a["proyectos"]),
        "Tesis dirigidas": [{"Año": t["producto"]["anio"], "Título": t["producto"]["titulo"],
                             "Tesista(s)": _nombres(t["tesistas"]),
                             "Nivel": estudiantes.NIVELES.get(t["nivel"], ""), "Estado": t["estado"],
                             "Del programa": "Sí" if any(x["del_programa"] for x in t["tesistas"]) else "No",
                             "Dirige": _nombres(t["directores"])} for t in a["estudiantes"]["tesis"]],
        "Productos con estudiantes": informes.filas_productos(a["estudiantes"]["productos"]),
        "3.5.2 Países de coautores": [{"País": k, "Artículos": v} for k, v in a["coautoria"]["por_pais"].items()],
        "Por confirmar": informes.filas_productos(m["por_confirmar"]),
        "Método": metodo})
    return _archivo(contenido, f"anexo-idi-{d}-{h}.xlsx", XLSX)
