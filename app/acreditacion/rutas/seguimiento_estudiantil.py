"""Anexo de seguimiento estudiantil (PLAN §49 y §50): documento imprimible con cifras agregadas y su XLSX. Lo ven quienes ven el
seguimiento estudiantil (Dirección de Carrera, Coordinación académica, Gestión de datos y Comité de acreditación)."""
from datetime import date
from urllib.parse import urlencode

from fasthtml.common import H1, H2, APIRouter, Div, P, Response, Table, Tbody, Td, Th, Thead, Tr

from app.acreditacion import seguimiento_estudiantil as seg
from app.acreditacion.rutas.informes import ESTILO_IMPRESION, XLSX, _archivo, _cifra, _selector_anio, barra, descarga, hoja
from app.comun import exportar, permisos, vinculos
from app.comun.componentes.layout import pagina
from app.estudiantil import actividad, encuestas

rt = APIRouter()


def _puede(auth) -> bool:
    return permisos.puede(auth, "ver_seguimiento_estudiantil", vinculos.carrera())


def _ventana(desde, hasta):
    d0, h0 = seg.ventana_por_omision()
    h = min(int(hasta), date.today().year) if str(hasta).isdigit() else h0
    d = int(desde) if str(desde).isdigit() else d0
    d, h = min(d, h), max(d, h)
    return max(d, h - 14), h


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f} %"


def _num(x, dec=1):
    return "—" if x is None else f"{x:.{dec}f}".replace(".", ",")


def _tabla(cabeceras, filas, vacio="Sin datos en el periodo."):
    if not filas:
        return P(vacio, cls="apagado")
    return Div(Table(Thead(Tr(*[Th(c, cls="text-right" if i else "") for i, c in enumerate(cabeceras)])),
                     Tbody(*[Tr(*[Td(str(v), cls="text-right tabular-nums" if i else "") for i, v in enumerate(f)]) for f in filas])),
               cls="overflow-x-auto")


def documento(i):
    c, a, t, e, d = i["cohortes"], i["actividad"], i["tutoria"], i["egresados"], i["directorio"]
    tot = c["totales"]
    return hoja(
        H1(f"Seguimiento estudiantil {i['desde']}–{i['hasta']}"),
        P("Cifras agregadas de los estudiantes y egresados de la licenciatura, a partir de lo que registra el sistema. No incluye nombres, "
          "notas ni materias. Las cohortes alimentan las hojas 3 a 6 de la Guía de Antecedentes de IAC-CINDA.", cls="apagado text-sm"),
        Div(_cifra(tot["total"], f"estudiantes con cohorte {i['desde']}–{i['hasta']}"), _cifra(tot["estados"]["cursando"], "cursando"),
            _cifra(tot["estados"]["titulado"], "titulados"), _cifra(tot["desertores"], "desertores"),
            cls="grid grid-cols-2 sm:grid-cols-4 gap-3 my-6"),
        H2("Cohortes de ingreso"),
        _tabla(["Cohorte", "Ingresaron", "Cursan", "Egresaron", "Titulados", "Desertores", "Tasa de egreso", "Tasa de titulación", "Tasa de deserción"],
               [(f["cohorte"], f["ingresaron"], f["cursan"], f["egresaron"], f["titulados"], f["desertores"], _pct(f["tasa_egreso"]),
                 _pct(f["tasa_titulacion"]), _pct(f["tasa_desercion"])) for f in c["filas"]], "No hay cohortes cargadas en el periodo."),
        P("Desertor: retirado, o congelado que no volvió en los dos ciclos siguientes. Las tasas son sobre los ingresantes de cada cohorte.",
          cls="apagado text-xs mt-2"),
        H2("Actividad estudiantil verificada"),
        _tabla(["Tipo", *[str(x) for x in a["anios"]]], [(actividad.TIPOS[tp], *[a["por_anio"][an].get(tp, 0) for an in a["anios"]])
                                                          for tp in a["tipos"]], "Aún no hay actividades verificadas en el periodo."),
        P(f"{a['pendientes']} actividad(es) declarada(s) por verificar no se cuentan.", cls="apagado text-xs mt-2") if a["pendientes"] else "",
        H2("Encuestas"),
        _tabla(["Encuesta", "Modalidad", "Año", "Invitadas", "Respondieron", "Tasa", "Promedio (1 a 5)"],
               [(f["titulo"], f["modalidad"], f["anio"], f["invitadas"], f["respondieron"], _pct(f["tasa"]),
                 "reservado" if f["oculto"] else _num(f["promedio_escalas"], 2)) for f in i["encuestas"]],
               "No hay encuestas abiertas ni cerradas en el periodo."),
        P(f"«Reservado»: encuesta anónima con menos de {encuestas.MIN_ANONIMO} respuestas; no se muestran resultados para no identificar a nadie. "
          "El promedio es el de los promedios de sus preguntas de escala.", cls="apagado text-xs mt-2"),
        H2("Tutoría"),
        Div(_cifra(_pct(t["cobertura"]), f"con tutor ({t['con_tutor']} de {t['cursando']})"), _cifra(t["tutores"], "tutores"),
            _cifra(t["reuniones"], "reuniones registradas"), _cifra(t["sin_reunion_12m"], "sin reunión en 12 meses"),
            cls="grid grid-cols-2 sm:grid-cols-4 gap-3 my-3"),
        P("Reuniones por año: " + (" · ".join(f"{an}: {n}" for an, n in t["por_anio"].items()) or "—") + ". Derivaciones: "
          + (" · ".join(f"{k}: {n}" for k, n in t["derivaciones"].items() if n) or "ninguna") + ". El contenido de las reuniones es confidencial "
          "y no figura en este informe.", cls="text-sm"),
        H2("Egresados"),
        _tabla(["Titulados en", "Titulados", "Años hasta titularse", "Respondieron", "Con empleo", "En su área", "Posgrado", "Utilidad", "Satisfacción"],
               [(f"{x['desde']}–{x['hasta']}", x["titulados"], _num(x["anios_medios"]), f"{x['respondieron']} ({_pct(x['tasa_respuesta'])})",
                 f"{_pct(x['empleo'])} (n = {x['n_situacion']})", _pct(x["en_el_area"]), f"{_pct(x['posgrado'])} (n = {x['n_posgrado']})",
                 _num(x["utilidad"], 2), _num(x["satisfaccion"], 2)) for x in e["trienios"]], "Aún no hay egresados titulados cargados."),
        P("Seguimiento a los 6 meses, 1, 3 y 5 años: " + " · ".join(f"{s['nombre']}: {s['respondidos']} de {s['invitados']} respondieron"
                                                                  for s in i["seguimiento"]) + ". Utilidad y satisfacción, de 1 a 5.", cls="apagado text-xs mt-2"),
        H2("Directorio de egresados y mentoría"),
        P(f"{d['visibles']} egresado(s) figuran en el directorio de {d['invitados']} invitado(s). Los estudiantes enviaron {d['solicitudes']} "
          f"solicitud(es) de mentoría, charlas, pasantías, orientación de posgrado u ofertas; {d['aceptadas']} fueron aceptadas.", cls="text-sm"))


@rt("/informes/seguimiento-estudiantil")
def get(auth, desde: str = "", hasta: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    d, h = _ventana(desde, hasta)
    anios = list(range(date.today().year, 1999, -1))
    q = urlencode({"desde": d, "hasta": h})
    return pagina(f"Seguimiento estudiantil {d}–{h}", ESTILO_IMPRESION,
                  barra([_selector_anio("desde", d, anios, "Desde"), _selector_anio("hasta", h, anios, "Hasta")],
                        [descarga("XLSX", f"/informes/seguimiento-estudiantil/xlsx?{q}")]),
                  documento(seg.informe(d, h)), usuario=auth, seccion="informes")


@rt("/informes/seguimiento-estudiantil/xlsx")
def get(auth, desde: str = "", hasta: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    d, h = _ventana(desde, hasta)
    return _archivo(exportar.a_xlsx(seg.filas_xlsx(seg.informe(d, h))), f"seguimiento-estudiantil-{d}-{h}.xlsx", XLSX)

