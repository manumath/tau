"""Informes de docencia: carga docente por semestre (`ver_carga`) e indicadores del cuerpo académico
por año (`ver_informes_institucionales`). Imprimibles y con descarga XLSX."""
from datetime import date
from urllib.parse import urlencode

import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, H1, H2, Option, P, Response, Select, Span, Table, Tbody, Td, Th, Thead, Tr

from app.academico import carga as carga_mod, gestiones
from app.acreditacion import cuerpo_academico as ca, informes
from app.acreditacion.rutas.informes import (ESTILO_IMPRESION, XLSX, _archivo, _cifra, _selector_anio, barra, descarga,
                                             hoja)
from app.comun import permisos, unidades, vinculos
from app.comun.componentes.layout import pagina

rt = APIRouter()
ACT = vinculos.ACTIVIDADES
ABREV = {"investigacion": "Inv.", "extension": "Ext.", "gestion": "Gest.", "otras": "Otras"}


def _num(v, sufijo=""):
    return Td("—" if v is None or v == "" else f"{v}{sufijo}", cls="text-right tabular-nums")


def _h(v):
    return _num(v or None)


# --- Carga docente ------------------------------------------------------------------------------------

def _semestres():
    return [g for g in gestiones.listar() if g["tipo"] in carga_mod.SEMESTRES]


def documento_carga(d):
    g, t, i = d["gestion"], d["total"], d["inscripciones"]
    filas = [Tr(Td(f["nombre"]), Td(f["categoria"], cls="text-sm"), _h(f["contratada"]), _num(f["jce"]),
                Td(f"{f['prevista'] if f['prevista'] is not None else '—'} / {f['asignada']}",
                   cls="text-right tabular-nums whitespace-nowrap"),
                *[_h(f[k]) for k in ca.ACTIVIDADES_NO_DOCENCIA],
                Td(f"{f['inv_proyectos'] + f['ext_proyectos']}" if f["inv_proyectos"] + f["ext_proyectos"] else "—",
                   cls="text-right tabular-nums"),
                Td("; ".join(a.split(" (")[0] for a in f["avisos"]) or "Completa",
                   cls="text-xs apagado" if not f["avisos"] else "text-xs"))
             for f in d["filas"]]
    categorias = [Tr(Td(c), _num(x["personas"]), _num(x["horas"]), _num(x["jce"]), _num(x["docencia"]),
                     *[_h(x[k]) for k in ca.ACTIVIDADES_NO_DOCENCIA]) for c, x in d["por_categoria"].items()]
    return hoja(
        P(f"{unidades.obtener(unidades.id_de(unidades.CARRERA))['nombre']} · {unidades.obtener(unidades.id_de('UMSA'))['nombre']}",
          cls="apagado text-sm uppercase tracking-wide"),
        H1(f"Carga docente {gestiones.codigo(g)}"),
        P(f"{gestiones.nombre(g)}, del {g['fecha_inicio']} al {g['fecha_fin']}. Carga en h/mes (unidades de 32); "
          "rige el vínculo vigente al inicio del semestre. JCE = carga contratada / 160.", cls="apagado text-sm"),
        Div(_cifra(t["personas"], "personas"), _cifra(t["jce"], "jornadas completas eq."),
            _cifra(f"{t['pct_investigacion']} %" if t["pct_investigacion"] is not None else "—", "de la carga en investigación"),
            _cifra(d["inscripciones_por_jce"] if d["inscripciones_por_jce"] is not None else "—", "inscripciones por JCE"),
            cls="grid grid-cols-2 sm:grid-cols-4 gap-3 my-6"),
        H2("Por categoría"),
        Div(Table(Thead(Tr(Th("Categoría"), Th("Personas", cls="text-right"), Th("h/mes", cls="text-right"),
                           Th("JCE", cls="text-right"), Th("Docencia", cls="text-right"),
                           *[Th(ACT[k], cls="text-right") for k in ca.ACTIVIDADES_NO_DOCENCIA])),
                  Tbody(*categorias,
                        Tr(Td("Total", cls="font-semibold"), _num(t["personas"]), _num(t["horas"]), _num(t["jce"]),
                           _num(t["docencia"]), *[_h(t[k]) for k in ca.ACTIVIDADES_NO_DOCENCIA]))),
            cls="overflow-x-auto"),
        H2("Por persona"),
        Div(Table(Thead(Tr(Th("Persona"), Th("Categoría"), Th("Contratada", cls="text-right"), Th("JCE", cls="text-right"),
                           Th("Docencia prevista / asignada", cls="text-right"),
                           *[Th(ABREV[k], cls="text-right", title=ACT[k]) for k in ca.ACTIVIDADES_NO_DOCENCIA],
                           Th("En proyectos", cls="text-right"), Th("Estado"))),
                  Tbody(*filas)), cls="overflow-x-auto") if filas
        else P("Nadie tiene vínculo con la Carrera ni materias en este semestre.", cls="apagado"),
        H2("Oferta del semestre"),
        P(f"{i['paralelos']} paralelos · {i['sin_docente']} sin docente titular · {i['inscritos']} inscripciones"
          + (f" ({i['sin_dato']} paralelos sin dato de inscritos)" if i["sin_dato"] else "") + ".", cls="text-sm"),
        P("Las inscripciones suman los inscritos de cada paralelo: quien cursa dos materias cuenta dos veces. No es la "
          "matrícula de la Carrera.", cls="apagado text-sm"))


@rt("/informes/carga-docente")
def get(auth, gestion: str = ""):
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    semestres = _semestres()
    g = next((x for x in semestres if str(x["id"]) == gestion), None) or carga_mod.semestre_de_referencia()
    if not g:
        return pagina("Carga docente", P("Todavía no hay semestres registrados.", cls="text-sm"),
                      usuario=auth, seccion="informes")
    filtro = fh.Label(Span("Semestre", cls="text-sm"),
                      Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=x["id"] == g["id"]) for x in semestres],
                             name="gestion", cls="uk-select w-36"), cls="flex items-center gap-2")
    return pagina(f"Carga docente {gestiones.codigo(g)}", ESTILO_IMPRESION,
                  barra([filtro], [descarga("XLSX", f"/informes/carga-docente/xlsx?gestion={g['id']}")]),
                  documento_carga(ca.carga_docente(g)), usuario=auth, seccion="informes")


@rt("/informes/carga-docente/xlsx")
def get(auth, gestion: str = ""):
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(int(gestion)) if gestion.isdigit() else carga_mod.semestre_de_referencia()
    if not g or g["tipo"] not in carga_mod.SEMESTRES:
        return Response("Semestre no encontrado", status_code=404)
    return _archivo(informes.a_xlsx(ca.filas_xlsx(ca.carga_docente(g))), f"carga-docente-{gestiones.codigo(g)}.xlsx", XLSX)


# --- Indicadores del cuerpo académico ---------------------------------------------------------------------

def _ventana(desde, hasta):
    h = int(hasta) if str(hasta).isdigit() else date.today().year
    d = int(desde) if str(desde).isdigit() else h - 4
    h = min(h, date.today().year)
    d, h = min(d, h), max(d, h)
    return (max(d, h - 10), h)


def _serie(titulo, clave, serie, sufijo=" %"):
    return Tr(Td(titulo), *[_num(x[clave], sufijo if x[clave] is not None else "") for x in serie])


def documento_indicadores(serie):
    anios = [x["anio"] for x in serie]
    categorias = sorted({c for x in serie for c in x["por_categoria"]})
    tramos = list(serie[0]["tramos"]) if serie else []
    ultimo = serie[-1]
    cab = Thead(Tr(Th(""), *[Th(str(a), cls="text-right") for a in anios]))
    return hoja(
        P(f"{unidades.obtener(unidades.id_de(unidades.CARRERA))['nombre']} · {unidades.obtener(unidades.id_de('UMSA'))['nombre']}",
          cls="apagado text-sm uppercase tracking-wide"),
        H1(f"Cuerpo académico {anios[0]}–{anios[-1]}"),
        P("Indicadores al 31 de diciembre de cada año (el año en curso, a hoy), con el vínculo con la Carrera vigente "
          "en esa fecha. Pensados para el criterio de cuerpo académico de IAC-CINDA.", cls="apagado text-sm"),
        Div(_cifra(ultimo["total"], f"académicos vinculados ({ultimo['anio']})"), _cifra(ultimo["jce"], "JCE"),
            _cifra(f"{ultimo['pct_doctores']} %" if ultimo["pct_doctores"] is not None else "—", "con doctorado"),
            _cifra(f"{ultimo['pct_con_proyecto']} %" if ultimo["pct_con_proyecto"] is not None else "—", "con proyecto vigente"),
            cls="grid grid-cols-2 sm:grid-cols-4 gap-3 my-6"),
        H2("Indicadores"),
        Div(Table(cab, Tbody(
            Tr(Td("Académicos vinculados"), *[_num(x["total"]) for x in serie]),
            Tr(Td("Jornadas completas equivalentes (160 h/mes)"), *[_num(x["jce"]) for x in serie]),
            _serie("Con doctorado", "pct_doctores", serie),
            _serie("Con posgrado (doctorado o maestría)", "pct_posgrado", serie),
            Tr(Td("Sin grado registrado"), *[_num(x["sin_grado"]) for x in serie]),
            _serie("Carga dedicada a investigación", "pct_investigacion", serie),
            _serie("Con proyecto vigente", "pct_con_proyecto", serie),
            Tr(Td("Inscripciones por JCE (semestre de referencia)"),
               *[_num(x["inscripciones_por_jce"]) for x in serie]))), cls="overflow-x-auto"),
        P("Semestre de referencia: el II del año si ya empezó; si no, el I. Las inscripciones suman los inscritos de "
          "cada paralelo. Carga en investigación: horas de investigación / horas contratadas de quienes tienen carga "
          "registrada.", cls="apagado text-xs mt-2"),
        H2("Por categoría"),
        Div(Table(cab, Tbody(*[Tr(Td(c), *[_num(x["por_categoria"].get(c, 0)) for x in serie]) for c in categorias])),
            cls="overflow-x-auto"),
        H2("Por tramo de edad"),
        Div(Table(cab, Tbody(*[Tr(Td(t), *[_num(x["tramos"][t]) for x in serie]) for t in tramos])),
            cls="overflow-x-auto"),
        P("Se calcula con la fecha de nacimiento, que el informe nunca muestra. «Sin dato»: la administración aún no "
          "la registró.", cls="apagado text-xs mt-2"),
        P(f"{ultimo['sin_jornada']} persona(s) sin carga ni jornada registrada en {ultimo['anio']}: no suman a la JCE."
          if ultimo["sin_jornada"] else "", cls="apagado text-xs"))


@rt("/informes/cuerpo-academico")
def get(auth, desde: str = "", hasta: str = ""):
    if not permisos.puede(auth, "ver_informes_institucionales"):
        return Response("No autorizado", status_code=403)
    d, h = _ventana(desde, hasta)
    anios = list(range(date.today().year, 1999, -1))
    q = urlencode({"desde": d, "hasta": h})
    return pagina(f"Cuerpo académico {d}–{h}", ESTILO_IMPRESION,
                  barra([_selector_anio("desde", d, anios, "Desde"), _selector_anio("hasta", h, anios, "Hasta")],
                        [descarga("XLSX", f"/informes/cuerpo-academico/xlsx?{q}")]),
                  documento_indicadores(ca.indicadores(d, h)), usuario=auth, seccion="informes")


@rt("/informes/cuerpo-academico/xlsx")
def get(auth, desde: str = "", hasta: str = ""):
    if not permisos.puede(auth, "ver_informes_institucionales"):
        return Response("No autorizado", status_code=403)
    d, h = _ventana(desde, hasta)
    return _archivo(informes.a_xlsx(ca.filas_indicadores(ca.indicadores(d, h))), f"cuerpo-academico-{d}-{h}.xlsx", XLSX)

