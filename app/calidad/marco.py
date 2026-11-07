"""Marco de calidad de una unidad (PLAN §57, etapa 2): marco → dimensiones → criterios → indicadores, con la escala de
valoración, los atributos (los criterios de calidad de la Política de Calidad de la UMSA) y las metas por año.

El marco es un dato, no código: lo carga la migración 0051 desde datos/calidad/marco-carrera/ y lo edita la Dirección
de Carrera. Las fuentes automáticas (`FUENTES_AUTOMATICAS`) son las cifras que el sistema calculará (etapa 3); un
indicador manual se registra a mano.
"""
import re

from app.calidad.marco_csv import CAMPOS_MARCO, COLUMNAS  # noqa: F401  (CAMPOS_MARCO lo usan las rutas)
from app.comun import exportar, permisos
from app.comun.db import HOY, get_db, transaccion

TIPOS = {"estructura": "Estructura", "proceso": "Proceso", "resultado": "Resultado", "percepcion": "Percepción",
         "contexto": "Contexto"}
FRECUENCIAS = {"anual": "Anual", "semestral": "Semestral", "por_periodo": "Por periodo de evaluación"}
SENTIDOS = {"mayor": "Mejor si sube", "menor": "Mejor si baja", "informativo": "Informativo (sin semáforo)"}

# clave → qué calcula. El cálculo llega con la etapa 3 (tablero de indicadores); por ahora sirven para validar.
FUENTES_AUTOMATICAS = {
    "paralelos_con_docente": "Paralelos con docente asignado (oferta del semestre)",
    "revisiones_calidad_datos": "Observaciones abiertas en «Calidad de datos»",
    "antiguedad_plan": "Años desde la aprobación del plan de estudios vigente",
    "observaciones_plan": "Inconsistencias abiertas del plan de estudios",
    "inscritos_por_paralelo": "Inscripciones por paralelo dictado",
    "ingresantes": "Ingresantes de la cohorte (tablero de cohortes)",
    "ingresantes_mujeres": "Porcentaje de mujeres entre los ingresantes",
    "retencion_primer_anio": "Retención al primer año de la cohorte",
    "desercion": "Deserción de la cohorte",
    "cobertura_tutoria": "Estudiantes cursando con tutor asignado",
    "brecha_desercion_genero": "Diferencia de deserción entre mujeres y hombres",
    "variacion_estudiantes_en_proyectos": "Variación anual de estudiantes vinculados a proyectos",
    "actividad_estudiantil": "Actividades estudiantiles verificadas",
    "jce": "Jornadas completas equivalentes",
    "inscripciones_por_jce": "Inscripciones por jornada completa equivalente",
    "pct_doctorado": "Académicos con doctorado",
    "pct_posgrado": "Académicos con posgrado",
    "pct_carga_investigacion": "Parte de la carga contratada dedicada a la investigación",
    "pct_60_o_mas": "Académicos de 60 años o más (por tramos de edad)",
    "retencion_doctores": "Doctores con vínculo continuo de más de 3 años",
    "proyectos_vigentes": "Proyectos de investigación vigentes",
    "pct_con_proyecto": "Académicos con proyecto vigente",
    "articulos_indexados": "Artículos en revistas indexadas",
    "variacion_indexados": "Variación anual de los artículos indexados",
    "indexados_por_jce": "Artículos indexados por jornada completa equivalente",
    "citas": "Citas de la producción (OpenAlex)",
    "tesis_defendidas": "Tesis dirigidas defendidas",
    "productos_con_estudiantes": "Productos con estudiantes o graduados como autores",
    "variacion_propiedad_intelectual": "Variación anual de los registros de propiedad intelectual",
    "transferencia": "Actividades de transferencia de conocimiento",
    "proyectos_interaccion_social": "Proyectos de interacción social vigentes",
    "variacion_transferencia_divulgacion": "Variación anual de las actividades de transferencia y divulgación",
    "servicios": "Prestaciones de servicios a terceros",
    "pct_coautoria_internacional": "Artículos con coautoría internacional",
    "redes": "Participación en redes de investigación",
    "estancias": "Estancias y pasantías de investigación",
    "titulacion_oportuna": "Titulación oportuna de la cohorte",
    "tiempo_titulacion": "Tiempo medio de titulación",
    "empleabilidad": "Egresados con empleo relacionado (seguimiento de egresados)",
    "continuidad_posgrado": "Egresados en estudios de posgrado",
    "satisfaccion_egresados": "Satisfacción de los egresados con la formación",
    "autoevaluacion_vigente": "Autoevaluación concluida en los últimos 5 años",
    "tasa_respuesta_encuestas": "Participación en las encuestas del año",
    "acciones_cumplidas": "Acciones del plan de mejora cumplidas en plazo",
    "cumplimiento_objetivos": "Indicadores con meta cumplida",
}

LARGO_CODIGO, LARGO_NOMBRE = 20, 200
_CODIGO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-_]*$")


# --- Lectura ------------------------------------------------------------------------------------------------

def puede(auth, accion: str, m: dict | None) -> bool:
    """Gestionar el marco (y cerrar sus años) es de la Dirección de Carrera de su unidad, y registrar cifras, de quien
    tenga la acción en esa unidad; verlo (solo lectura, sin datos personales) lo pueden quienes tengan
    `ver_marco_calidad` (o `ver_evidencias_calidad`) en cualquier unidad: la Dirección del Instituto responde por los indicadores de investigación
    de la Carrera."""
    if m is None:
        return False
    return permisos.puede(auth, accion, None if accion.startswith("ver_") else m["unidad_id"])


def de_unidad(unidad_id: int) -> dict | None:
    """El marco vigente de la unidad: el de vigencia más reciente que no terminó; si no hay, el último creado."""
    filas = get_db().q(
        f"""SELECT * FROM marco_calidad WHERE unidad_id = ?
            ORDER BY (vigente_hasta IS NOT NULL AND vigente_hasta < {HOY}), vigente_desde DESC, id DESC""",
        [unidad_id])
    return filas[0] if filas else None


def obtener(mid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM marco_calidad WHERE id = ?", [mid])
    return filas[0] if filas else None


def escala(mid: int) -> list[dict]:
    return get_db().q("SELECT * FROM nivel_escala WHERE marco_id = ? ORDER BY valor", [mid])


def atributos(mid: int) -> list[dict]:
    return get_db().q("SELECT * FROM atributo_calidad WHERE marco_id = ? ORDER BY nombre", [mid])


def dimensiones(mid: int) -> list[dict]:
    return get_db().q("SELECT * FROM dimension_calidad WHERE marco_id = ? ORDER BY codigo", [mid])


def dimension(did: int) -> dict | None:
    filas = get_db().q("SELECT * FROM dimension_calidad WHERE id = ?", [did])
    return filas[0] if filas else None


def criterio(cid: int) -> dict | None:
    filas = get_db().q(
        """SELECT c.*, d.marco_id, d.codigo AS dimension_codigo, d.nombre AS dimension_nombre
           FROM criterio_calidad c JOIN dimension_calidad d ON d.id = c.dimension_id WHERE c.id = ?""", [cid])
    return filas[0] if filas else None


def indicador(iid: int) -> dict | None:
    filas = get_db().q(
        """SELECT i.*, c.codigo AS criterio_codigo, c.nombre AS criterio_nombre, d.id AS dimension_id,
                  d.codigo AS dimension_codigo, d.nombre AS dimension_nombre, d.marco_id
           FROM indicador_calidad i JOIN criterio_calidad c ON c.id = i.criterio_id
           JOIN dimension_calidad d ON d.id = c.dimension_id WHERE i.id = ?""", [iid])
    if not filas:
        return None
    x = filas[0]
    x["atributos"] = get_db().q(
        """SELECT a.* FROM indicador_atributo ia JOIN atributo_calidad a ON a.id = ia.atributo_id
           WHERE ia.indicador_id = ? ORDER BY a.nombre""", [iid])
    x["metas"] = metas(iid)
    return x


def metas(iid: int) -> list[dict]:
    return get_db().q("SELECT * FROM meta_indicador WHERE indicador_id = ? ORDER BY anio", [iid])


def arbol(mid: int, atributo: str | None = None, inactivos: bool = True) -> list[dict]:
    """Dimensiones con sus criterios y, en cada uno, sus indicadores (con atributos y metas). Con `atributo` (clave),
    solo los indicadores marcados con él, y solo los criterios y dimensiones que tienen alguno."""
    db = get_db()
    inds = db.q(
        """SELECT i.*, c.dimension_id FROM indicador_calidad i JOIN criterio_calidad c ON c.id = i.criterio_id
           JOIN dimension_calidad d ON d.id = c.dimension_id WHERE d.marco_id = ? ORDER BY i.codigo""", [mid])
    marcas = {}
    for f in db.q("""SELECT ia.indicador_id, a.clave, a.nombre FROM indicador_atributo ia
                     JOIN atributo_calidad a ON a.id = ia.atributo_id WHERE a.marco_id = ? ORDER BY a.nombre""", [mid]):
        marcas.setdefault(f["indicador_id"], []).append(f)
    todas_metas = {}
    for f in db.q("""SELECT m.* FROM meta_indicador m JOIN indicador_calidad i ON i.id = m.indicador_id
                     JOIN criterio_calidad c ON c.id = i.criterio_id JOIN dimension_calidad d ON d.id = c.dimension_id
                     WHERE d.marco_id = ? ORDER BY m.anio""", [mid]):
        todas_metas.setdefault(f["indicador_id"], []).append(f)
    por_criterio = {}
    for i in inds:
        i["atributos"], i["metas"] = marcas.get(i["id"], []), todas_metas.get(i["id"], [])
        if (not inactivos and not i["activo"]) or (atributo and atributo not in {a["clave"] for a in i["atributos"]}):
            continue
        por_criterio.setdefault(i["criterio_id"], []).append(i)
    res = []
    for d in dimensiones(mid):
        d["criterios"] = []
        for c in db.q("SELECT * FROM criterio_calidad WHERE dimension_id = ? ORDER BY codigo", [d["id"]]):
            c["indicadores"] = por_criterio.get(c["id"], [])
            if not atributo or c["indicadores"]:
                d["criterios"].append(c)
        if not atributo or d["criterios"]:
            res.append(d)
    return res


def resumen(mid: int) -> dict:
    """Cuántas dimensiones, criterios e indicadores (activos, automáticos y manuales) tiene el marco."""
    f = get_db().q(
        """SELECT (SELECT COUNT(*) FROM dimension_calidad WHERE marco_id = :m) AS dimensiones,
                  (SELECT COUNT(*) FROM criterio_calidad c JOIN dimension_calidad d ON d.id = c.dimension_id
                    WHERE d.marco_id = :m) AS criterios,
                  COUNT(i.id) AS indicadores, COALESCE(SUM(i.activo), 0) AS activos,
                  COALESCE(SUM(i.activo AND i.fuente LIKE 'auto:%'), 0) AS automaticos
           FROM indicador_calidad i JOIN criterio_calidad c ON c.id = i.criterio_id
           JOIN dimension_calidad d ON d.id = c.dimension_id WHERE d.marco_id = :m""", {"m": mid})[0]
    f["manuales"] = f["activos"] - f["automaticos"]
    return f


def fuente_texto(fuente: str) -> str:
    if fuente.startswith("auto:"):
        return "Automática: " + FUENTES_AUTOMATICAS.get(fuente[5:], fuente[5:])
    return "Manual (se registra a mano)"


# --- Validación ---------------------------------------------------------------------------------------------

def _texto(d, k):
    return (d.get(k) or "").strip()


def _codigo(d, errores, existentes, propio=None):
    codigo = _texto(d, "codigo")
    if not codigo:
        errores.append("Indique el código.")
    elif len(codigo) > LARGO_CODIGO or not _CODIGO.match(codigo):
        errores.append(f"El código admite letras, números, puntos y guiones (hasta {LARGO_CODIGO} caracteres).")
    elif codigo.lower() in {c.lower() for c, i in existentes if i != propio}:
        errores.append(f"Ya hay otro elemento con el código «{codigo}» en este marco.")
    return codigo


def _nombre(d, errores):
    nombre = _texto(d, "nombre")
    if not nombre:
        errores.append("Indique el nombre.")
    elif len(nombre) > LARGO_NOMBRE:
        errores.append(f"El nombre admite hasta {LARGO_NOMBRE} caracteres.")
    return nombre


def validar_marco(d: dict) -> tuple[dict, list[str]]:
    errores = []
    x = {"nombre": _nombre(d, errores), "version": _texto(d, "version"), "descripcion": _texto(d, "descripcion") or None,
         "vigente_desde": _texto(d, "vigente_desde") or None, "vigente_hasta": _texto(d, "vigente_hasta") or None}
    if not x["version"]:
        errores.append("Indique la versión (por ejemplo, «2027» o «2027-aprobada»).")
    try:
        x["ventana_anios"] = int(_texto(d, "ventana_anios") or 5)
        if not 1 <= x["ventana_anios"] <= 10:
            raise ValueError
    except ValueError:
        x["ventana_anios"] = _texto(d, "ventana_anios")
        errores.append("La ventana de evidencia es de 1 a 10 años.")
    if x["vigente_desde"] and x["vigente_hasta"] and x["vigente_hasta"] < x["vigente_desde"]:
        errores.append("La vigencia termina antes de empezar.")
    return x, errores


def validar_escala(texto: str) -> tuple[list[dict], list[str]]:
    """Un nivel por línea, del más bajo al más alto: «Nombre: descripción» (la descripción es opcional)."""
    niveles = []
    for linea in (texto or "").splitlines():
        if linea.strip():
            nombre, _, descripcion = linea.partition(":")
            niveles.append({"valor": len(niveles) + 1, "nombre": nombre.strip(), "descripcion": descripcion.strip() or None})
    errores = []
    if not 2 <= len(niveles) <= 7:
        errores.append("La escala debe tener de 2 a 7 niveles, uno por línea.")
    if any(not n["nombre"] for n in niveles):
        errores.append("Cada nivel necesita un nombre antes de los dos puntos.")
    return niveles, errores


def _codigos_dimensiones(mid):
    return [(f["codigo"], f["id"]) for f in dimensiones(mid)]


def _codigos_criterios(mid):
    return [(f["codigo"], f["id"]) for f in get_db().q(
        "SELECT c.codigo, c.id FROM criterio_calidad c JOIN dimension_calidad d ON d.id = c.dimension_id "
        "WHERE d.marco_id = ?", [mid])]


def _codigos_indicadores(mid):
    return [(f["codigo"], f["id"]) for f in get_db().q(
        "SELECT i.codigo, i.id FROM indicador_calidad i JOIN criterio_calidad c ON c.id = i.criterio_id "
        "JOIN dimension_calidad d ON d.id = c.dimension_id WHERE d.marco_id = ?", [mid])]


def validar_dimension(d: dict, mid: int, did: int | None = None) -> tuple[dict, list[str]]:
    errores = []
    x = {"codigo": _codigo(d, errores, _codigos_dimensiones(mid), did), "nombre": _nombre(d, errores),
         "descripcion": _texto(d, "descripcion") or None, "referencia": _texto(d, "referencia") or None}
    return x, errores


def validar_criterio(d: dict, mid: int, cid: int | None = None) -> tuple[dict, list[str]]:
    errores = []
    x = {"codigo": _codigo(d, errores, _codigos_criterios(mid), cid), "nombre": _nombre(d, errores),
         "descripcion": _texto(d, "descripcion") or None}
    return x, errores


def validar_indicador(d: dict, mid: int, iid: int | None = None) -> tuple[dict, list[str]]:
    errores = []
    x = {"codigo": _codigo(d, errores, _codigos_indicadores(mid), iid), "nombre": _nombre(d, errores),
         "tipo": _texto(d, "tipo"), "formula": _texto(d, "formula") or None,
         "fuente": _texto(d, "fuente") or "manual", "unidad_medida": _texto(d, "unidad_medida") or None,
         "frecuencia": _texto(d, "frecuencia") or "anual", "sentido": _texto(d, "sentido") or "mayor",
         "responsable": _texto(d, "responsable") or None, "referencia": _texto(d, "referencia") or None}
    if x["tipo"] not in TIPOS:
        errores.append("Elija el tipo de indicador.")
    if x["fuente"] != "manual" and (not x["fuente"].startswith("auto:") or x["fuente"][5:] not in FUENTES_AUTOMATICAS):
        errores.append("Elija una fuente de la lista.")
    if x["frecuencia"] not in FRECUENCIAS:
        errores.append("Elija la frecuencia.")
    if x["sentido"] not in SENTIDOS:
        errores.append("Elija cómo se lee el indicador.")
    if not x["formula"]:
        errores.append("Describa la fórmula: cómo se calcula la cifra.")
    validos = {a["id"] for a in atributos(mid)}
    x["atributos"] = sorted({int(a) for a in d.get("atributos") or [] if str(a).isdigit() and int(a) in validos})
    return x, errores


def validar_meta(anio: str, valor: str, nota: str = "", que: str = "meta") -> tuple[dict, list[str]]:
    errores = []
    x = {"anio": (anio or "").strip(), "valor": (valor or "").strip().replace(",", "."), "nota": (nota or "").strip() or None}
    try:
        x["anio"] = int(x["anio"])
        if not 2000 <= x["anio"] <= 2100:
            raise ValueError
    except ValueError:
        errores.append(f"Indique el año de la {que}.")
    try:
        x["valor"] = float(x["valor"])
    except ValueError:
        errores.append(f"La {que} es un número (use punto o coma para los decimales).")
    return x, errores


# --- Escritura ----------------------------------------------------------------------------------------------

def guardar_marco(mid: int, x: dict):
    get_db().t.marco_calidad.update({k: x[k] for k in CAMPOS_MARCO + ("vigente_hasta",)}, mid)


def guardar_escala(mid: int, niveles: list[dict]):
    with transaccion():
        get_db().execute("DELETE FROM nivel_escala WHERE marco_id = ?", [mid])
        for n in niveles:
            get_db().t.nivel_escala.insert(marco_id=mid, **n)


def crear_dimension(mid: int, x: dict) -> int:
    return get_db().t.dimension_calidad.insert(marco_id=mid, **x)["id"]


def actualizar_dimension(did: int, x: dict):
    get_db().t.dimension_calidad.update(x, did)


def eliminar_dimension(did: int) -> bool:
    """Solo una dimensión sin criterios ni síntesis de una autoevaluación."""
    if get_db().q("""SELECT 1 FROM criterio_calidad WHERE dimension_id = :d
                     UNION ALL SELECT 1 FROM sintesis_dimension WHERE dimension_id = :d LIMIT 1""", {"d": did}):
        return False
    get_db().execute("DELETE FROM dimension_calidad WHERE id = ?", [did])
    return True


def crear_criterio(did: int, x: dict) -> int:
    return get_db().t.criterio_calidad.insert(dimension_id=did, **x)["id"]


def actualizar_criterio(cid: int, x: dict):
    get_db().t.criterio_calidad.update(x, cid)


def eliminar_criterio(cid: int) -> bool:
    """Solo un criterio sin indicadores, evidencias ni juicios de una autoevaluación."""
    if get_db().q("""SELECT 1 FROM indicador_calidad WHERE criterio_id = :c
                     UNION ALL SELECT 1 FROM evidencia_criterio WHERE criterio_id = :c
                     UNION ALL SELECT 1 FROM juicio_criterio WHERE criterio_id = :c LIMIT 1""", {"c": cid}):
        return False
    get_db().execute("DELETE FROM criterio_calidad WHERE id = ?", [cid])
    return True


def _atributos(iid: int, ids: list[int]):
    get_db().execute("DELETE FROM indicador_atributo WHERE indicador_id = ?", [iid])
    for a in ids:
        get_db().t.indicador_atributo.insert(indicador_id=iid, atributo_id=a)


def crear_indicador(cid: int, x: dict) -> int:
    datos = {k: v for k, v in x.items() if k != "atributos"}
    with transaccion():
        iid = get_db().t.indicador_calidad.insert(criterio_id=cid, **datos)["id"]
        _atributos(iid, x["atributos"])
    return iid


def actualizar_indicador(iid: int, x: dict):
    with transaccion():
        get_db().t.indicador_calidad.update({k: v for k, v in x.items() if k != "atributos"}, iid)
        _atributos(iid, x["atributos"])


def activar_indicador(iid: int, activo: bool):
    get_db().execute("UPDATE indicador_calidad SET activo = ? WHERE id = ?", [int(activo), iid])


def eliminar_indicador(iid: int) -> bool:
    """Solo un indicador sin metas (con metas, se desactiva). Desde la etapa 3, también sin cifras registradas."""
    if metas(iid):
        return False
    get_db().execute("DELETE FROM indicador_calidad WHERE id = ?", [iid])
    return True


def guardar_meta(iid: int, x: dict):
    get_db().execute(
        """INSERT INTO meta_indicador (indicador_id, anio, valor, nota) VALUES (?, ?, ?, ?)
           ON CONFLICT (indicador_id, anio) DO UPDATE SET valor = excluded.valor, nota = excluded.nota""",
        [iid, x["anio"], x["valor"], x["nota"]])


def eliminar_meta(iid: int, anio: int):
    get_db().execute("DELETE FROM meta_indicador WHERE indicador_id = ? AND anio = ?", [iid, anio])


# --- Exportación --------------------------------------------------------------------------------------------

def a_xlsx(mid: int) -> bytes:
    """El marco en XLSX, una hoja por archivo del formato de carga (marco_csv) y una de metas."""
    m = obtener(mid)
    arb = arbol(mid)
    hojas = {
        "Marco": [{"campo": k, "valor": m[k] if m[k] is not None else ""} for k in CAMPOS_MARCO + ("vigente_hasta",)],
        "Escala": [{k: n[k] for k in COLUMNAS["escala"]} for n in escala(mid)],
        "Atributos": [{k: a[k] for k in COLUMNAS["atributos"]} for a in atributos(mid)],
        "Dimensiones": [{k: d[k] for k in COLUMNAS["dimensiones"]} for d in arb],
        "Criterios": [{"dimension": d["codigo"], **{k: c[k] for k in COLUMNAS["criterios"][1:]}}
                      for d in arb for c in d["criterios"]],
        "Indicadores": [{"criterio": c["codigo"], **{k: i[k] for k in COLUMNAS["indicadores"][1:-1]},
                         "atributos": "|".join(a["clave"] for a in i["atributos"]), "activo": "sí" if i["activo"] else "no"}
                        for d in arb for c in d["criterios"] for i in c["indicadores"]],
        "Metas": [{"indicador": i["codigo"], "anio": mt["anio"], "valor": mt["valor"], "nota": mt["nota"] or ""}
                  for d in arb for c in d["criterios"] for i in c["indicadores"] for mt in i["metas"]],
    }
    return exportar.a_xlsx(hojas)
