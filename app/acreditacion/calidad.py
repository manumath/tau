"""Calidad de datos (PLAN.md, sección 31): lo que falta o no cuadra antes de generar informes.

Cada chequeo dice qué revisa, a qué afecta (el anexo, la docencia, los informes), quién lo corrige y
qué registros lo incumplen, con un enlace para corregirlos. No cambia nada: solo consulta. Reutiliza
las reglas de los informes (p. ej., `informes.memoria(...)["por_confirmar"]`) para no duplicarlas.
"""
from datetime import date
from urllib.parse import quote

from app.academico import carga
from app.acreditacion import anexo, informes
from app.comun import academicos, personas, vinculos
from app.comun.db import get_db
from app.investigacion import perfiles

QUIEN = {"carrera": "Dirección de Carrera", "instituto": "Dirección del Instituto",
         "administracion": "Administración del sistema", "personas": "Cada persona (en su perfil o sus registros)",
         "responsables": "Responsables de proyecto"}
MAX_ITEMS = 50


def _chequeo(clave, grupo, titulo, explicacion, quien, afecta, items):
    return {"clave": clave, "grupo": grupo, "titulo": titulo, "explicacion": explicacion, "quien": quien,
            "afecta": afecta, "items": items[:MAX_ITEMS], "n": len(items)}


def _item(texto, href, detalle=None):
    return {"texto": texto, "href": href, "detalle": detalle}


def _persona(f):
    """Texto y enlace a la persona en «Usuarios» (desde ahí se abren su vínculo y su ficha)."""
    return f"{f['apellidos']}, {f['nombres']}", f"/admin/usuarios?q={quote(f['apellidos'])}"


def _vigentes() -> list[dict]:
    h = vinculos.hoy().isoformat()
    return get_db().q(
        """SELECT DISTINCT u.id, u.nombres, u.apellidos FROM vinculo v JOIN usuario u ON u.id = v.usuario_id
           WHERE COALESCE(v.fecha_inicio, '0000-01-01') <= ? AND COALESCE(v.fecha_fin, '9999-12-31') >= ?
           ORDER BY u.apellidos, u.nombres""", [h, h])


# --- Vínculos y carga ---------------------------------------------------------------------------------

def sin_termino():
    filas = get_db().q(
        f"""SELECT v.usuario_id, v.categoria, v.fecha_inicio, u.nombres, u.apellidos FROM vinculo v
            JOIN usuario u ON u.id = v.usuario_id
            WHERE v.fecha_fin IS NULL AND v.categoria IN ({",".join("?" * len(vinculos.CON_TERMINO))})
            ORDER BY u.apellidos""", list(vinculos.CON_TERMINO))
    return _chequeo("sin_termino", "Vínculos y carga", "Periodos sin fecha de término",
                    "Contratados, interinos e invitados se vinculan por un periodo definido.", "carrera",
                    "Vigencia de la categoría y de la carga", [
                        _item(*_persona(f), f"{vinculos.CATEGORIAS[f['categoria']]} desde {f['fecha_inicio'] or '?'}")
                        for f in filas])


def sin_carga():
    return _chequeo("sin_carga", "Vínculos y carga", "Docentes con vínculo vigente sin carga contratada",
                    "Titulares, contratados e interinos deberían tener su carga horaria registrada.", "carrera",
                    "Carga docente, JCE del anexo", [
                        _item(*_persona(f), vinculos.CATEGORIAS[f["categoria"]]) for f in carga.vigentes_sin_carga()])


def sin_ingreso():
    return _chequeo("sin_ingreso", "Vínculos y carga", "Vínculos sin fecha de ingreso",
                    "Sin fecha de inicio no se sabe desde cuándo cuenta su producción.", "carrera",
                    "Memoria y anexo (producción a la fecha)", [
                        _item(*_persona(f)) for f in vinculos.sin_fecha_de_ingreso()])


def investigadores_sin_vinculo():
    filas = get_db().q(
        f"""SELECT u.id, u.nombres, u.apellidos FROM usuario u JOIN investigador i ON i.usuario_id = u.id
            WHERE u.activo = 1 AND {vinculos.sql_categoria_vigente('u')} IS NULL ORDER BY u.apellidos""")
    return _chequeo("investigadores_sin_vinculo", "Vínculos y carga", "Investigadores activos sin vínculo vigente",
                    "Su producción de hoy no cuenta en los informes hasta que tengan vínculo.", "carrera",
                    "Memoria y anexo", [_item(*_persona(f)) for f in filas])


# --- Personas -----------------------------------------------------------------------------------------

def sin_grado():
    items = [_item(*_persona(p)) for p in _vigentes() if not academicos.grados(p["id"])]
    return _chequeo("sin_grado", "Personas", "Académicos vinculados sin grado registrado",
                    "El porcentaje de doctores y de posgrado se calcula con los grados.", "personas",
                    "Indicadores del cuerpo académico", items)


def sin_nacimiento():
    items = [_item(*_persona(p)) for p in _vigentes() if not academicos.fecha_nacimiento(p["id"])]
    return _chequeo("sin_nacimiento", "Personas", "Académicos vinculados sin fecha de nacimiento",
                    "Los tramos de edad del cuerpo académico la necesitan (el informe nunca la muestra).",
                    "administracion", "Indicadores del cuerpo académico (tramos de edad)", items)


def perfiles_incompletos():
    items = []
    for p in _vigentes():
        perfil = perfiles.obtener(p["id"])
        if not perfil:
            continue
        pct, faltan = perfiles.completitud(perfil, len(perfiles.areas(p["id"])))
        if "ORCID" in faltan or pct < 50:
            items.append(_item(f"{p['apellidos']}, {p['nombres']}", f"/investigadores/{p['id']}",
                               f"{pct} % · falta: {', '.join(faltan)}"))
    return _chequeo("perfiles", "Personas", "Perfiles de investigación incompletos (sin ORCID o bajo el 50 %)",
                    "El ORCID permite cargar y verificar la producción; el perfil alimenta el CV y el directorio.",
                    "personas", "CV, directorio, carga desde OpenAlex", items)


# --- Producción ---------------------------------------------------------------------------------------

def productos_por_confirmar():
    d, h = anexo.ventana_por_omision()
    m = informes.memoria(desde=f"{d}-01-01", hasta=f"{h}-12-31", exigir_verificada=True)
    items = [_item(f"{x['titulo']} ({x['anio']})", f"/productos/{x['id']}", x["motivo"]) for x in m["por_confirmar"]]
    return _chequeo("por_confirmar", "Producción", f"Publicaciones que no cuentan hasta completarse ({d}–{h})",
                    "Filiación sin declarar, revista sin verificar en el catálogo o mes faltante cuando el "
                    "vínculo cubre solo parte del año.", "personas", "Memoria y anexo de I+D+i", items)


# --- Docencia -----------------------------------------------------------------------------------------

def oferta_incompleta():
    g = carga.semestre_de_referencia()
    if not g:
        return _chequeo("oferta", "Docencia", "Oferta del semestre", "", "carrera", "Carga docente", [])
    filas = get_db().q(
        """SELECT a.sigla, a.nombre, o.paralelo, o.inscritos,
                  EXISTS (SELECT 1 FROM oferta_docente d WHERE d.oferta_id = o.id AND d.rol = 'titular') AS con_docente
           FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id WHERE o.gestion_id = ?
           ORDER BY a.sigla, o.paralelo""", [g["id"]])
    href = f"/docencia/oferta?gestion={g['id']}"
    items = [_item(f"{f['sigla']} {f['paralelo']} · {f['nombre']}", href,
                   " y ".join(x for x in ("sin docente titular" if not f["con_docente"] else "",
                                          "sin inscritos registrados" if f["inscritos"] is None else "") if x))
             for f in filas if not f["con_docente"] or f["inscritos"] is None]
    codigo = f"{g['tipo']}-{g['anio']}"
    return _chequeo("oferta", "Docencia", f"Paralelos de {codigo} sin docente titular o sin inscritos",
                    "La carga docente y las inscripciones por JCE usan la oferta.", "carrera",
                    "Carga docente e indicadores", items)


def observaciones_de_planes():
    filas = get_db().q(
        """SELECT o.detalle, p.id AS plan_id, p.nombre AS plan, pr.nombre AS programa FROM observacion_plan o
           JOIN plan_estudios p ON p.id = o.plan_id JOIN programa pr ON pr.id = p.programa_id
           WHERE o.estado = 'pendiente' ORDER BY pr.nombre, o.id""")
    return _chequeo("planes", "Docencia", "Observaciones de los planes de estudio por revisar",
                    "Inconsistencias de los documentos oficiales, cargadas tal cual.", "carrera",
                    "Planes de estudio", [_item(f"{f['programa']} · {f['plan']}", f"/docencia/planes/{f['plan_id']}",
                                                f["detalle"]) for f in filas])


# --- Proyectos ----------------------------------------------------------------------------------------

def proyectos_sin_ambito():
    filas = get_db().q("""SELECT p.id, p.nombre FROM proyecto p WHERE p.estado = 'vigente' AND p.ambito IS NULL
                          AND NOT EXISTS (SELECT 1 FROM proyecto_contraparte c WHERE c.proyecto_id = p.id)
                          ORDER BY p.nombre""")
    return _chequeo("sin_ambito", "Proyectos", "Proyectos vigentes sin ámbito (nacional o internacional)",
                    "Sin ámbito ni contrapartes no se sabe si es internacional.", "responsables",
                    "Anexo (proyectos internacionales)", [_item(f["nombre"], f"/proyectos/{f['id']}") for f in filas])


def proyectos_sin_lineas():
    filas = get_db().q("""SELECT p.id, p.nombre FROM proyecto p WHERE p.estado = 'vigente' AND p.tipo = 'institucional'
                          AND p.clase = 'investigacion'
                          AND NOT EXISTS (SELECT 1 FROM proyecto_linea l WHERE l.proyecto_id = p.id)
                          ORDER BY p.nombre""")
    return _chequeo("sin_lineas", "Proyectos", "Proyectos de investigación vigentes sin línea de investigación",
                    "Los proyectos de investigación se adscriben a las líneas institucionales.", "responsables",
                    "Líneas de investigación", [_item(f["nombre"], f"/proyectos/{f['id']}") for f in filas])


def externos_duplicados():
    pares = personas.posibles_duplicados()
    return _chequeo("externos_duplicados", "Producción", "Coautores externos posiblemente duplicados",
                    "Dos fichas de una misma persona cuentan dos veces en coautoría e internacionalización.",
                    "instituto", "Indicadores de coautoría e internacionalización (3.5.2)",
                    [_item(f"{p['a']['apellidos']}, {p['a']['nombres']} · {p['b']['apellidos']}, {p['b']['nombres']}",
                           "/personas/externos/duplicados", p["motivo"]) for p in pares])


def externos_con_cuenta():
    sugerencias = personas.sugerencias_de_cuenta()
    return _chequeo("externos_con_cuenta", "Producción", "Coautores externos que ya tienen cuenta",
                    "Lo que registraron como externos no cuenta como producción del instituto hasta vincularlo a su cuenta.",
                    "instituto", "Memoria, anexo y CV de esas personas",
                    [_item(f"{s['externo']['apellidos']}, {s['externo']['nombres']} → {s['usuario']['apellidos']}, "
                           f"{s['usuario']['nombres']}", "/personas/externos/duplicados", s["motivo"]) for s in sugerencias])


CHEQUEOS = (sin_termino, sin_carga, sin_ingreso, investigadores_sin_vinculo, sin_grado, sin_nacimiento,
            perfiles_incompletos, productos_por_confirmar, externos_duplicados, externos_con_cuenta, oferta_incompleta,
            observaciones_de_planes, proyectos_sin_ambito, proyectos_sin_lineas)


def revisar() -> list[dict]:
    return [c() for c in CHEQUEOS]


def resumen(chequeos: list[dict] | None = None) -> dict:
    chequeos = chequeos if chequeos is not None else revisar()
    con = [c for c in chequeos if c["n"]]
    return {"chequeos": len(chequeos), "con_observaciones": len(con), "registros": sum(c["n"] for c in con),
            "por_quien": {q: sum(c["n"] for c in con if c["quien"] == q) for q in QUIEN}, "fecha": date.today()}
