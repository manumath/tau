"""Lo que el módulo de informes de investigación aporta al menú y al inicio (PLAN §73)."""
from datetime import date

from app.comun import permisos
from app.comun.componentes.bandeja import nombres, plural
from app.comun.db import get_db
from app.comun.menu import item
from app.informes import anexo, calidad_datos, programados

G = "Calidad"


def menu_informes(auth):
    puede = lambda accion: permisos.puede(auth, accion)  # noqa: E731
    items = []
    if auth["es_investigador"] or puede("ver_informes_institucionales") or puede("ver_cv_ajeno"):
        items.append((G, 10, item("informes", "Informes", "/informes", "file-text")))
    if puede("ver_calidad_datos"):
        items.append((G, 110, item("calidad", "Calidad de datos", "/informes/calidad", "list-checks")))
    return items


def inicio_informes(auth):
    """Académicos sin grado (para quien gestiona fichas sin ver la calidad de datos) y registros por completar."""
    items = []
    if permisos.puede(auth, "gestionar_fichas") and not permisos.puede(auth, "ver_calidad_datos"):
        c = calidad_datos.sin_grado()   # las direcciones lo ven en «Calidad de datos»
        if c["n"]:
            items.append(("fichas", 10, {
                "texto": f"{plural(c['n'], 'académico vinculado', 'académicos vinculados')} sin grado registrado",
                "href": "/admin/usuarios",
                "detalle": nombres([{"nombres": i["texto"].split(", ")[-1], "apellidos": i["texto"].split(", ")[0]}
                                    for i in c["items"]])}))
    if permisos.puede(auth, "ver_calidad_datos"):
        r = calidad_datos.resumen()
        if r["registros"]:
            items.append(("calidad_datos", 10, {
                "texto": f"{plural(r['registros'], 'registro')} por completar en {r['con_observaciones']} de "
                         f"{r['chequeos']} revisiones", "href": "/informes/calidad",
                "detalle": "Antes de generar la memoria o el informe de I+D+i."}))
    return items


def cifras_informes(auth):
    """Quien ve los informes institucionales: el cuerpo académico del año."""
    if not permisos.puede(auth, "ver_informes_institucionales"):
        return []
    anio = date.today().year
    cuerpo = anexo.cuerpo_academico(anio, date.today().isoformat())
    vigentes = get_db().q("SELECT COUNT(*) n FROM proyecto WHERE estado = 'vigente'")[0]["n"]
    return [(20, f"Aseguramiento de la Calidad · {anio}", [
        (cuerpo["total"], "académicos vinculados", "/informes/cuerpo-academico"),
        (cuerpo["jce"], "jornadas completas eq.", "/informes/cuerpo-academico"),
        (vigentes, "proyectos vigentes", "/informes/memoria"),
        ("Informe", "de I+D+i", "/informes/investigacion")])]


MANTENIMIENTO = [lambda: programados.mantenimiento()]    # informes que se envían solos
