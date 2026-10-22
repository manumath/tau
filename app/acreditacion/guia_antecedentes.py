"""Guía de Antecedentes de IAC-CINDA (pregrado, 2025) llenada con lo que registra el sistema.

Se parte de la plantilla oficial vacía (`datos/iac-cinda/`) y se escriben solo las celdas de datos
(`app.comun.xlsx_plantilla`): la estructura, las fórmulas y los gráficos del «Resumen estadístico»
quedan como los entrega IAC-CINDA. Lo que el sistema no registra (admisión, cohortes, egreso y
titulación, consejo, becas, bienestar, recursos, impacto de cada actividad…) queda en blanco para
completarlo a mano; `COBERTURA` lo dice hoja por hoja.

Decisiones (PLAN §36): horas en h/semana (h/mes ÷ 4); jornada completa ≥ 160 h/mes, media 80–159,
por horas < 80; montos en USD con el tipo de cambio que indica quien genera la guía; «académicos
del programa»: vínculo con la Carrera como titular, contratado(a), interino(a) o invitado(a).
"""
from datetime import date

from app.academico import gestiones, planes
from app.acreditacion import anexo
from app.acreditacion import estudiantes as ind_estudiantes
from app.acreditacion.cuerpo_academico import _grado_hasta
from app.comun import academicos, adscripcion, config, estudiantes, vinculos
from app.comun.db import get_db
from app.comun.xlsx_plantilla import Plantilla
from app.investigacion import actividades, lineas, productos, proyectos, revistas

PLANTILLA = config.RAIZ / "datos" / "iac-cinda" / "Guia-de-Antecedentes-pregrado-2025.xlsx"
CATEGORIAS = ("titular", "contratado", "interino", "invitado")   # académicos del programa
N_CICLOS = 10
H = {  # nombres de las hojas en la plantilla (algunos terminan en espacio)
    "id": "1. Identificación carrera", "lineas": "2. Líneas de investigación ",
    "cohortes": "4. Cohortes ciclo-semestre", "egresados": "5.Egresados ciclo-semestre",
    "titulados": "6. Titulados ciclo-semestre", "asignaturas": "7.a. Asignaturas y actividades ",
    "optativas": "7.b. Asignaturas optativas", "academicos": "10. Académicos",
    "caracterizacion": "11. Caracterización académicos ", "jefes": "12. Jefes de práctica",
    "desarrollo": "19. Desarrollo académico", "proyectos": "20. Proyectos de investigación",
    "profesional": "21. Desarrollo profesional", "articulos": "22. Artículos",
    "libros": "23. Libros o Capítulos de libro", "patentes": "25. Patentes", "redes": "26. Redes",
    "extension": "27. Extensión", "servicios": "28. Prestación de servicios",
}
# Qué llena el sistema en cada hoja (se muestra en la pantalla de la guía).
COBERTURA = [
    ("0. Resumen estadístico", "Se calcula solo en Excel a partir de las demás hojas."),
    ("1. Identificación", "Programa, institución, créditos u horas del plan, área OCDE y los 10 ciclos. "
                          "Falta: matrícula, sede, jornada, modalidad, duración oficial y año de inicio."),
    ("2. Líneas de investigación", "Las líneas vigentes. Falta: perfiles de ingreso y egreso y objetivos."),
    ("3 a 6. Admisión, cohortes, egreso y titulación", "No: son datos del sistema académico de la UMSA. El "
                                                       "sistema solo ajusta los ciclos y corrige las fórmulas."),
    ("7.a y 7.b. Asignaturas", "Del plan vigente: semestre, requisitos, créditos y veces que se dictó en el último "
                               "año. Falta: cupo por sección y línea formativa."),
    ("8 y 9. Plan de estudios y consejo", "No."),
    ("10. Académicos", "Grados, edad, incorporación, unidad, categoría, horas por actividad, cursos, tesis y premios. "
                       "Falta: sistema nacional de investigación."),
    ("11. Caracterización", "Por ciclo: jornada, horas de docencia, grado, edad y categoría."),
    ("12. Jefes de práctica", "Auxiliares de docencia registrados en la oferta del último año. Falta: horas."),
    ("13 a 18. Perfeccionamiento, personal, becas, bienestar y recursos", "No."),
    ("19. Desarrollo académico", "Congresos, seminarios, talleres, escuelas y estancias. Falta: impacto y "
                                 "financiamiento."),
    ("20. Proyectos de investigación", "Datos, equipo, estudiantes y financiamiento. Falta: impacto y difusión."),
    ("21. Desarrollo profesional", "Actividades de transferencia de conocimiento."),
    ("22, 23 y 25. Artículos, libros y patentes", "Casi completas. Falta: ISBN y fechas de las patentes."),
    ("24. Obras de creación", "No aplica."),
    ("26. Redes", "Participación en redes. Falta: actividades, productos y difusión."),
    ("27. Extensión", "Proyectos de interacción social y actividades de divulgación. Falta: impacto y evaluación."),
    ("28. Prestación de servicios", "Servicios registrados como actividades: contraparte, responsables, "
                                    "participantes y montos en USD. Falta: impacto, evaluación y difusión."),
]


# --- Ciclos -------------------------------------------------------------------------------------------

def texto_ciclo(anio: int, tipo: str) -> str:
    return f"{anio}-{tipo}"


def ciclos_hasta(anio: int, tipo: str, n: int = N_CICLOS) -> list[tuple[int, str]]:
    """Los `n` semestres (I, II) que terminan en el indicado, del más antiguo al más reciente."""
    res, a, t = [], anio, tipo
    for _ in range(n):
        res.append((a, t))
        a, t = (a, "I") if t == "II" else (a - 1, "II")
    return list(reversed(res))


def ultimo_ciclo_por_omision() -> tuple[int, str]:
    """El último semestre (I o II) que ya empezó."""
    hoy = date.today().isoformat()
    filas = get_db().q("""SELECT anio, tipo FROM gestion_academica WHERE tipo IN ('I', 'II') AND fecha_inicio <= ?
                          ORDER BY fecha_inicio DESC LIMIT 1""", [hoy])
    if filas:
        return filas[0]["anio"], filas[0]["tipo"]
    y = date.today().year
    return (y, "II") if hoy >= f"{y}-08-01" else (y, "I")


def _inicio(anio: int, tipo: str) -> str:
    g = gestiones.por_codigo(f"{tipo}-{anio}")
    return g["fecha_inicio"] if g else gestiones.fechas_por_omision(anio, tipo)[0]


# --- Utilidades ------------------------------------------------------------------------------------

def _nombres(personas) -> str:
    return "; ".join(f"{p['nombres']} {p['apellidos']}" for p in personas)


def _usd(monto, moneda: str | None, tipo_cambio: float | None):
    if monto is None:
        return None
    if (moneda or "").upper() == "USD":
        return monto
    if (moneda or "").upper() in ("BOB", "BS") and tipo_cambio:
        return round(monto / tipo_cambio, 2)
    return None


def _h_semana(h_mes) -> int | float | None:
    if not h_mes:
        return None
    v = h_mes / 4
    return int(v) if v == int(v) else v


def _horas_vinculo(v: dict) -> int | None:
    return v.get("horas_contratadas") or (v["jornada_horas"] * 4 if v.get("jornada_horas") else None)


def _jornada(h_mes) -> str:
    if h_mes and h_mes >= 160:
        return "completa"
    if h_mes and h_mes >= 80:
        return "media"
    return "horas"


def _academico(uid: int, fecha: str) -> dict | None:
    v = vinculos.vigente(uid, fecha)
    return v if v and v["categoria"] in CATEGORIAS else None


def _es_del_programa(uid: int, anio: int, mes: int | None = None) -> bool:
    estado, categoria = vinculos.en_fecha(uid, anio, mes)
    return estado == "si" and categoria in CATEGORIAS


def planes_vigentes() -> list[dict]:
    """Planes vigentes de licenciatura: la Guía se llena por programa (IAC-CINDA acredita cada uno)."""
    return [p for p in planes.listar() if p["nivel"] == "licenciatura" and p["vigente_hasta"] is None]


# --- Hojas ---------------------------------------------------------------------------------------

def _identificacion(x: Plantilla, plan, ciclos):
    h = H["id"]
    x.escribir(h, "B7", config.UNIVERSIDAD)
    # Duración oficial: la completa la Dirección (decisión del 1-oct-2026); la plantilla trae un 5 de ejemplo.
    x.escribir(h, "B12", None)
    x.escribir(h, "A19", "CIENCIAS_NATURALES")
    x.escribir(h, "B19", "1.1. MATEMÁTICAS")
    if plan:
        x.escribir(h, "B6", plan["programa"])
        t = planes.totales(plan["id"])
        if "en créditos" in t:
            x.escribir(h, "B13", t["en créditos"][0] or t["en créditos"][1])
        else:
            x.escribir(h, "B14", sum((d or c or 0) for d, c in t.values()))
    for i, (a, t) in enumerate(ciclos):
        x.escribir(h, f"B{30 + i}", texto_ciclo(a, t))


def _lineas(x: Plantilla, hasta: str):
    for i, linea in enumerate(lineas.vigentes(hasta)):
        x.escribir(H["lineas"], f"A{26 + i}", i + 1)
        x.escribir(H["lineas"], f"B{26 + i}", linea["nombre"] + (f": {linea['descripcion']}" if linea["descripcion"] else ""))


def _cohortes(x: Plantilla, ciclos):
    """Ciclos de las hojas 4 a 6 y fórmulas corregidas (la plantilla apunta a otro libro en 5 y 6 y
    usa la fila equivocada en la deserción al tercer año de la cohorte de la fila 18)."""
    previos = ciclos_hasta(*ciclos[-1], n=20)          # 19 cohortes + el último ciclo
    for i, (ca, ct) in enumerate(previos[:-1]):
        x.escribir(H["cohortes"], f"A{8 + i}", texto_ciclo(ca, ct))
    x.formula(H["cohortes"], "AA18", "(L18-R18)/L18")
    for hoja, fila_cab, fila_ini in ((H["egresados"], 6, 7), (H["titulados"], 8, 9)):
        for j, (ca, ct) in enumerate(ciclos):
            x.escribir(hoja, f"{chr(66 + j)}{fila_cab}", texto_ciclo(ca, ct))
        for i, (ca, ct) in enumerate(previos[:10]):
            x.escribir(hoja, f"A{fila_ini + i}", texto_ciclo(ca, ct))
            f = x.valor_original(hoja, f"L{fila_ini + i}")
            if f and "[1]" in f:
                x.formula(hoja, f"L{fila_ini + i}", f.replace("'[1]4.b.Cohortes semestre-ciclo'", f"'{H['cohortes']}'"))
            f = x.valor_original(hoja, f"M{fila_ini + i}")
            if f and "[1]" in f:
                x.formula(hoja, f"M{fila_ini + i}", f.replace("'[1]4.b.Cohortes semestre-ciclo'", f"'{H['cohortes']}'"))
    x.quitar_vinculos_externos()


def _asignaturas(x: Plantilla, plan, anio_ref: int):
    if not plan:
        return
    dictado = {f["asignatura_id"]: f for f in get_db().q(
        """SELECT o.asignatura_id, COUNT(DISTINCT o.gestion_id) AS veces
           FROM oferta o JOIN gestion_academica g ON g.id = o.gestion_id WHERE g.anio = ?
           GROUP BY o.asignatura_id""", [anio_ref])}
    filas = planes.asignaturas(plan["id"])
    obligatorias = [f for f in filas if f["semestre"] is not None]
    for i, f in enumerate(obligatorias):
        r = 7 + i
        d = dictado.get(f["asignatura_id"]) or {}
        nombre = f"{f['nombre']} ({f['sigla']})" if f["asignatura_id"] else planes.TIPOS[f["tipo"]]
        x.escribir(H["asignaturas"], f"A{r}", i + 1)
        x.escribir(H["asignaturas"], f"B{r}", f["semestre"])
        x.escribir(H["asignaturas"], f"C{r}", nombre)
        x.escribir(H["asignaturas"], f"D{r}", "sí" if f["requisitos"] else "no")
        x.escribir(H["asignaturas"], f"E{r}", d.get("veces"))
        x.escribir(H["asignaturas"], f"I{r}", f["creditos"])
        obs = [planes.TIPOS[f["tipo"]]] if f["tipo"] != "obligatoria" else []
        if f["requisitos"]:
            obs.append("Requisitos: " + ", ".join(f["requisitos"]))
        x.escribir(H["asignaturas"], f"J{r}", "; ".join(obs) or None)
    electivas = [f for grupo in planes.electivas(plan["id"]).values() for f in grupo]
    for i, f in enumerate(electivas):
        r = 6 + i
        d = dictado.get(f["asignatura_id"]) or {}
        x.escribir(H["optativas"], f"A{r}", i + 1)
        x.escribir(H["optativas"], f"B{r}", planes.GRUPOS_ELECTIVAS[f["tipo"]])
        x.escribir(H["optativas"], f"C{r}", f"{f['nombre']} ({f['sigla']})")
        x.escribir(H["optativas"], f"F{r}", f["creditos"])


def _cursos(uid: int, anio_ini: int, anio_fin: int, rol: str = "titular") -> dict[str, list[str]]:
    """{nombre de la asignatura: [ciclos]} dictados en los años."""
    res = {}
    for f in get_db().q(
            """SELECT a.nombre, a.sigla, g.anio, g.tipo FROM oferta_docente od JOIN oferta o ON o.id = od.oferta_id
               JOIN asignatura a ON a.id = o.asignatura_id JOIN gestion_academica g ON g.id = o.gestion_id
               WHERE od.usuario_id = ? AND od.rol = ? AND g.anio BETWEEN ? AND ?
               ORDER BY g.fecha_inicio""", [uid, rol, anio_ini, anio_fin]):
        res.setdefault(f"{f['nombre']} ({f['sigla']})", []).append(texto_ciclo(f["anio"], f["tipo"]))
    return res


def _texto_cursos(cursos: dict) -> str:
    return "; ".join(f"{n} ({', '.join(c)})" for n, c in cursos.items())


def academicos_al(fecha: str) -> list[tuple[dict, dict]]:
    """[(persona, vínculo)] de los académicos del programa a la fecha, por apellido."""
    res = []
    for u in vinculos.personas_en_rango("0000-01-01", fecha):
        v = _academico(u["id"], fecha)
        if v:
            res.append((u, v))
    return sorted(res, key=lambda x: (x[0]["apellidos"], x[0]["nombres"]))


def _academicos(x: Plantilla, anio_ini: int, anio_fin: int, corte: str):
    h = H["academicos"]
    tesis = ind_estudiantes.tesis(anio_ini, anio_fin)
    premios_del_programa = _actividades_del_programa(f"{anio_ini}-01-01", corte, anexo.PREMIOS)
    for i, (u, v) in enumerate(academicos_al(corte)):
        r = 7 + i
        uid = u["id"]
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", anio_fin)
        x.escribir(h, f"C{r}", u["apellidos"])
        x.escribir(h, f"D{r}", u["nombres"])
        for j, g in enumerate(academicos.grados(uid)[:3]):
            x.escribir(h, f"{'EGI'[j]}{r}", g["titulo"] or g["nivel_texto"])
            x.escribir(h, f"{'FHJ'[j]}{r}", ", ".join(y for y in (g["institucion"], g["pais"]) if y) or None)
        nacimiento = academicos.fecha_nacimiento(uid)
        x.escribir(h, f"K{r}", academicos.edad(nacimiento, corte) if nacimiento else None)
        inicios = [p["fecha_inicio"] for p in vinculos.listar(uid) if p["fecha_inicio"]]
        x.escribir(h, f"L{r}", int(min(inicios)[:4]) if inicios else None)
        x.escribir(h, f"M{r}", adscripcion.unidad(uid))
        categoria = vinculos.categoria_texto(v["categoria"])
        x.escribir(h, f"N{r}", categoria)
        x.escribir(h, f"P{r}", categoria + (" (permanente)" if not v["fecha_fin"] else f" (hasta el {v['fecha_fin']})"))
        x.escribir(h, f"Q{r}", _h_semana(v["carga_gestion"]))
        x.escribir(h, f"R{r}", _h_semana(v["carga_docencia"]))
        x.escribir(h, f"S{r}", _h_semana(v["carga_investigacion"]))
        x.escribir(h, f"T{r}", _h_semana((v["carga_extension"] or 0) + (v["carga_otras"] or 0)))
        cursos = _cursos(uid, anio_ini, anio_fin)
        x.escribir(h, f"V{r}", len(cursos))
        x.escribir(h, f"W{r}", _texto_cursos(cursos) or None)
        propias = [t for t in tesis if any(d["id"] == uid for d in t["directores"])]
        x.escribir(h, f"X{r}", len(propias))
        x.escribir(h, f"Y{r}", "; ".join(f"{t['producto']['titulo']} ({t['producto']['anio']})" for t in propias) or None)
        premios = [a for a in premios_del_programa if any(p["id"] == uid for p in a["internos"])]
        x.escribir(h, f"Z{r}", "; ".join(f"{a['titulo']}" + (f", {a['institucion']}" if a["institucion"] else "")
                                         + f" ({a['fecha_inicio'][:4]})" for a in premios) or None)
        obs = []
        if not _horas_vinculo(v):
            obs.append("Sin carga contratada registrada")
        elif not v.get("horas_contratadas"):
            obs.append("Horas según la jornada del vínculo (sin distribución por actividad)")
        if v["carga_extension"]:
            obs.append(f"«Otras» incluye {_h_semana(v['carga_extension'])} h/semana de extensión")
        x.escribir(h, f"AA{r}", "; ".join(obs) or None)


GRADOS_11 = (("doctorado",), ("maestria",), ("licenciatura", "especialidad"))


def _caracterizacion(x: Plantilla, ciclos):
    h = H["caracterizacion"]
    for col, cat in zip(("AC", "AD", "AE", "AF", "AG"), (*CATEGORIAS, None)):
        x.escribir(h, f"{col}8", vinculos.categoria_texto(cat) if cat else None)
    for i, (a, t) in enumerate(ciclos):
        r = 9 + i
        fecha = _inicio(a, t)
        x.escribir(h, f"A{r}", texto_ciclo(a, t))
        grupos = {"completa": [], "media": [], "horas": []}
        edades, por_cat, sin_carga = [0, 0, 0, 0], dict.fromkeys(CATEGORIAS, 0), 0
        for u, v in academicos_al(fecha):
            horas = _horas_vinculo(v)
            if not horas:
                sin_carga += 1
            grupos[_jornada(horas)].append((u, v))
            por_cat[v["categoria"]] += 1
            nacimiento = academicos.fecha_nacimiento(u["id"])
            if nacimiento:
                e = academicos.edad(nacimiento, fecha)
                edades[0 if e <= 35 else 1 if e <= 50 else 2 if e <= 65 else 3] += 1
        # El número de docentes de cada jornada (B, I, P) y el total (W) son fórmulas de la plantilla
        # que suman las columnas de grado.
        for jornada, (hmax, hmin, *grados) in (
                ("completa", ("C", "D", "E", "F", "G", "H")), ("media", ("J", "K", "L", "M", "N", "O")),
                ("horas", ("Q", "R", "S", "T", "U", "V"))):
            gente = grupos[jornada]
            docencia = [v["carga_docencia"] for _, v in gente if v.get("horas_contratadas")]
            x.escribir(h, f"{hmax}{r}", _h_semana(max(docencia)) if docencia else None)
            x.escribir(h, f"{hmin}{r}", _h_semana(min(docencia)) if docencia else None)
            niveles = [_grado_hasta(u["id"], a) for u, _ in gente]
            for col, grupo in zip(grados[:3], GRADOS_11):
                x.escribir(h, f"{col}{r}", sum(nv in grupo for nv in niveles))
            x.escribir(h, f"{grados[3]}{r}", sum(nv not in {g for gr in GRADOS_11 for g in gr} for nv in niveles))
        for col, n in zip(("Y", "Z", "AA", "AB"), edades):
            x.escribir(h, f"{col}{r}", n)
        for col, cat in zip(("AC", "AD", "AE", "AF"), CATEGORIAS):
            x.escribir(h, f"{col}{r}", por_cat[cat])
        obs = []
        if sin_carga:
            obs.append(f"{sin_carga} sin carga contratada registrada (contados por horas)")
        total = sum(len(g) for g in grupos.values())
        sin_edad = total - sum(edades)
        if sin_edad:
            obs.append(f"{sin_edad} sin fecha de nacimiento registrada")
        x.escribir(h, f"AH{r}", "; ".join(obs) or None)


def _jefes_practica(x: Plantilla, anio: int):
    h = H["jefes"]
    filas = get_db().q(
        """SELECT DISTINCT u.* FROM oferta_docente od JOIN oferta o ON o.id = od.oferta_id
           JOIN gestion_academica g ON g.id = o.gestion_id JOIN usuario u ON u.id = od.usuario_id
           WHERE od.rol = 'auxiliar' AND g.anio = ? ORDER BY u.apellidos, u.nombres""", [anio])
    for i, u in enumerate(filas):
        r = 9 + i
        cursos = _cursos(u["id"], anio - 4, anio, rol="auxiliar")
        grados = academicos.grados(u["id"])
        nacimiento = academicos.fecha_nacimiento(u["id"])
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", anio)
        x.escribir(h, f"C{r}", u["apellidos"])
        x.escribir(h, f"D{r}", u["nombres"])
        x.escribir(h, f"E{r}", (grados[0]["titulo"] or grados[0]["nivel_texto"]) if grados else None)
        x.escribir(h, f"F{r}", academicos.edad(nacimiento, f"{anio}-12-31") if nacimiento else None)
        x.escribir(h, f"H{r}", config.NOMBRE_CARRERA)
        x.escribir(h, f"I{r}", "Auxiliar de docencia")
        x.escribir(h, f"K{r}", len(cursos))
        x.escribir(h, f"L{r}", _texto_cursos(cursos) or None)


def _internos(personas_, anio: int, mes: int | None = None) -> list[dict]:
    return [p for p in personas_ if p["interno"] and _es_del_programa(p["id"], anio, mes)]


def _actividades_del_programa(desde: str, hasta: str, tipos) -> list[dict]:
    """Actividades de los tipos con al menos un académico del programa, en la fecha de inicio."""
    res = []
    for f in get_db().q(
            f"""SELECT a.id FROM actividad a JOIN tipo_actividad t ON t.id = a.tipo_id
                WHERE a.fecha_inicio BETWEEN ? AND ? AND t.nombre IN ({','.join('?' * len(tipos))})
                ORDER BY a.fecha_inicio""", [desde, hasta, *tipos]):
        a = actividades.obtener(f["id"])
        anio, mes = int(a["fecha_inicio"][:4]), int(a["fecha_inicio"][5:7])
        internos = _internos(actividades.participantes(a["id"]), anio, mes)
        if internos:
            res.append({**a, "internos": internos})
    return res


def _desarrollo(x: Plantilla, desde: str, hasta: str):
    h = H["desarrollo"]
    for i, a in enumerate(_actividades_del_programa(desde, hasta, (*anexo.EVENTOS, *anexo.ESTANCIAS))):
        r = 10 + i
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", a["tipo"])
        x.escribir(h, f"C{r}", a["titulo"])
        x.escribir(h, f"D{r}", a["lugar"])
        x.escribir(h, f"E{r}", a["pais"])
        x.escribir(h, f"F{r}", a["institucion"])
        x.escribir(h, f"G{r}", int(a["fecha_inicio"][:4]))
        x.escribir(h, f"H{r}", a["fecha_inicio"])
        x.escribir(h, f"I{r}", a["fecha_fin"] or a["fecha_inicio"])
        x.escribir(h, f"J{r}", lineas.nombres(lineas.de_registro("actividad", a["id"])) or None)
        x.escribir(h, f"K{r}", _nombres(a["internos"]))
        x.escribir(h, f"L{r}", "; ".join(actividades.ROLES.get(p["rol"], p["rol"]) for p in a["internos"]))
        x.escribir(h, f"M{r}", sum(1 for p in a["internos"] if _jornada(_horas_vinculo(
            vinculos.vigente(p["id"], a["fecha_inicio"]) or {})) == "completa"))
        x.escribir(h, f"N{r}", sum(1 for p in a["internos"] if _jornada(_horas_vinculo(
            vinculos.vigente(p["id"], a["fecha_inicio"]) or {})) != "completa"))


def _proyectos_del_programa(desde: str, hasta: str, clase: str) -> list[dict]:
    """Proyectos vigentes en el periodo con al menos un académico del programa. `clase`:
    'investigacion' (individuales e institucionales de investigación) o 'interaccion_social'."""
    res = []
    for p in proyectos.todos():
        if p["estado"] == "formulacion" or (p["fecha_inicio"] or "0000") > hasta or (p["fecha_fin"] or "9999") < desde:
            continue
        es_social = p["tipo"] == "institucional" and p.get("clase") == "interaccion_social"
        if es_social != (clase == "interaccion_social"):
            continue
        partes = proyectos.participantes(p["id"])
        corte = min(p["fecha_fin"] or hasta, hasta)
        internos = [x for x in partes if x["interno"] and (_academico(x["id"], corte) or _academico(x["id"], desde))]
        if internos:
            res.append({**p, "participantes": partes, "internos": internos})
    return sorted(res, key=lambda p: (p["fecha_inicio"] or "", p["nombre"]))


def _proyectos(x: Plantilla, desde: str, hasta: str, tipo_cambio: float | None):
    h = H["proyectos"]
    # La plantilla suma AQ+AR (columnas de difusión) como costo total: debe ser interno + externo.
    for r in range(9, 59):
        x.formula(h, f"AW{r}", f"SUM(AT{r}:AU{r})")
    for i, p in enumerate(_proyectos_del_programa(desde, hasta, "investigacion")):
        r = 9 + i
        partes, internos = p["participantes"], p["internos"]
        corte = min(p["fecha_fin"] or hasta, hasta)
        resp = [x for x in partes if x["rol"] == "responsable"]
        co = [x for x in partes if x["rol"] == "co_responsable"]
        otros_int = [x for x in internos if x["rol"] not in ("responsable", "co_responsable")]
        completa = [x for x in otros_int if _jornada(_horas_vinculo(_academico(x["id"], corte) or {})) == "completa"]
        parcial = [x for x in otros_int if x not in completa]
        externos = [x for x in partes if not x["interno"] and x["rol"] not in ("tesista",)]
        anio = int(corte[:4])
        pre = [x for x in partes if (e := estudiantes.estudiante_de(x, anio)) and e["nivel"] == "licenciatura"]
        pos = [x for x in partes if (e := estudiantes.estudiante_de(x, anio)) and e["nivel"] != "licenciatura"]
        meses = None
        if p["fecha_inicio"] and p["fecha_fin"]:
            a0, a1 = date.fromisoformat(p["fecha_inicio"]), date.fromisoformat(p["fecha_fin"])
            meses = (a1.year - a0.year) * 12 + a1.month - a0.month + 1
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", int(p["fecha_inicio"][:4]) if p["fecha_inicio"] else None)
        x.escribir(h, f"C{r}", int(p["fecha_fin"][:4]) if p["fecha_fin"] else None)
        x.escribir(h, f"D{r}", meses)
        x.escribir(h, f"E{r}", (f"{p['codigo']} — " if p["codigo"] else "") + p["nombre"])
        x.escribir(h, f"F{r}", proyectos.tipo_texto(p))
        x.escribir(h, f"G{r}", p["objetivo_general"] or p["descripcion"])
        x.escribir(h, f"H{r}", lineas.nombres(lineas.de_proyecto(p["id"])) or None)
        x.escribir(h, f"I{r}", _nombres(resp) or None)
        x.escribir(h, f"J{r}", _nombres(co) or None)
        x.escribir(h, f"K{r}", "; ".join(config.UNIVERSIDAD for _ in co) or None)
        x.escribir(h, f"L{r}", "; ".join(config.NOMBRE_CARRERA for _ in co) or None)
        x.escribir(h, f"M{r}", _nombres(completa) or None)
        x.escribir(h, f"N{r}", len(completa))
        x.escribir(h, f"O{r}", _nombres(parcial) or None)
        x.escribir(h, f"P{r}", len(parcial))
        x.escribir(h, f"T{r}", _nombres(externos) or None)
        x.escribir(h, f"U{r}", "; ".join(e.get("afiliacion") or "—" for e in externos) or None)
        x.escribir(h, f"V{r}", len(externos))
        x.escribir(h, f"X{r}", sum(x["rol"] == "postdoc" for x in partes))
        x.escribir(h, f"AE{r}", len(pre))
        x.escribir(h, f"AG{r}", sum(x["rol"] == "tesista" for x in pre))
        x.escribir(h, f"AJ{r}", len(pos))
        monto = _usd(p["monto"], p["moneda"], tipo_cambio)
        institucional = p["tipo"] == "institucional"
        x.escribir(h, f"AT{r}", monto if institucional else None)
        x.escribir(h, f"AU{r}", None if institucional else monto)
        x.escribir(h, f"AV{r}", None if institucional else p["fuente_financiamiento"])


def _productos_del_programa(anio_ini: int, anio_fin: int, tipos) -> list[dict]:
    """Productos de los tipos, enviados, aceptados o publicados en los años, con al menos un autor
    del programa (vínculo vigente en la fecha de publicación)."""
    res = []
    for p in productos.obtener_varios(f["id"] for f in get_db().q(
            f"""SELECT p.id FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
                WHERE p.anio BETWEEN ? AND ? AND t.nombre IN ({','.join('?' * len(tipos))})
                  AND p.estado_publicacion IN ('enviado', 'aceptado', 'publicado')
                ORDER BY p.anio, p.titulo""", [anio_ini, anio_fin, *tipos])):
        internos = _internos(p["autores"], p["anio"], p["mes"])
        if internos:
            res.append({**p, "internos": internos,
                        "externos": [a for a in p["autores"] if not any(a is i for i in internos)]})
    return res


def _comunes_producto(p) -> dict:
    return {"lineas": lineas.nombres(lineas.de_registro("producto", p["id"])) or None,
            "proyectos": "; ".join(v["proyecto"] for v in proyectos.vinculos_de("producto", p["id"])
                                   if v["estado"] == "aprobado") or None,
            "link": p["url"] or (f"https://doi.org/{p['doi']}" if p["doi"] else None)
            or (f"https://arxiv.org/abs/{p['arxiv_id']}" if p["arxiv_id"] else None)}


ESTADOS = {"enviado": "enviado", "aceptado": "aceptado", "publicado": "publicado"}


def _articulos(x: Plantilla, anio_ini: int, anio_fin: int):
    h = H["articulos"]
    for i, p in enumerate(_productos_del_programa(anio_ini, anio_fin, anexo.TIPOS_ARTICULO)):
        r = 6 + i
        c = _comunes_producto(p)
        d = revistas.detalle(p)
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", p["anio"])
        x.escribir(h, f"C{r}", p["titulo"])
        x.escribir(h, f"D{r}", _nombres(p["internos"]))
        x.escribir(h, f"E{r}", _nombres(p["externos"]) or None)
        x.escribir(h, f"F{r}", c["lineas"])
        x.escribir(h, f"G{r}", c["proyectos"])
        x.escribir(h, f"H{r}", "artículo" if p["tipo"] == "Artículo en revista" else "conference paper")
        x.escribir(h, f"I{r}", d["revista"] or p["medio"])
        x.escribir(h, f"J{r}", d["ambito"].lower() if d["ambito"] in ("Nacional", "Internacional") else None)
        x.escribir(h, f"K{r}", ", ".join(i_["nombre"] for i_ in p["indices"]) or productos.REVISIONES[p["revision"]])
        x.escribir(h, f"M{r}", ESTADOS[p["estado_publicacion"]])
        x.escribir(h, f"N{r}", d["issn"])
        x.escribir(h, f"O{r}", p["doi"])
        x.escribir(h, f"P{r}", c["link"])


def _libros(x: Plantilla, anio_ini: int, anio_fin: int):
    h = H["libros"]
    for i, p in enumerate(_productos_del_programa(anio_ini, anio_fin, ("Libro", "Capítulo de libro"))):
        r = 6 + i
        c = _comunes_producto(p)
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", p["anio"])
        x.escribir(h, f"C{r}", p["tipo"].lower())
        x.escribir(h, f"D{r}", p["titulo"])
        x.escribir(h, f"E{r}", _nombres(p["autores"]))
        x.escribir(h, f"F{r}", c["lineas"])
        x.escribir(h, f"I{r}", "no" if p["revision"] == "sin_arbitraje" else "sí")
        x.escribir(h, f"J{r}", p["medio"])
        x.escribir(h, f"K{r}", ESTADOS[p["estado_publicacion"]])
        x.escribir(h, f"M{r}", c["link"])


def _patentes(x: Plantilla, anio_ini: int, anio_fin: int):
    h = H["patentes"]
    for i, p in enumerate(_productos_del_programa(anio_ini, anio_fin, ("Patente",))):
        r = 6 + i
        c = _comunes_producto(p)
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", p["anio"])
        x.escribir(h, f"C{r}", p["titulo"])
        x.escribir(h, f"D{r}", _nombres(p["autores"]))
        x.escribir(h, f"E{r}", c["lineas"])
        x.escribir(h, f"I{r}", "concedida" if p["estado_publicacion"] == "publicado" else "solicitada")
        x.escribir(h, f"K{r}", c["link"])


def _profesional(x: Plantilla, desde: str, hasta: str):
    h = H["profesional"]
    for i, a in enumerate(_actividades_del_programa(desde, hasta, anexo.TRANSFERENCIA)):
        r = 8 + i
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", int(a["fecha_inicio"][:4]))
        x.escribir(h, f"C{r}", a["fecha_inicio"])
        x.escribir(h, f"D{r}", a["fecha_fin"] or a["fecha_inicio"])
        x.escribir(h, f"E{r}", _nombres(a["internos"]))
        x.escribir(h, f"F{r}", a["tipo"])
        x.escribir(h, f"G{r}", a["titulo"] + (f". {a['descripcion']}" if a["descripcion"] else ""))
        x.escribir(h, f"H{r}", lineas.nombres(lineas.de_registro("actividad", a["id"])) or None)
        x.escribir(h, f"I{r}", a["institucion"])
        x.escribir(h, f"L{r}", a["url"])


def _redes(x: Plantilla, desde: str, hasta: str):
    h = H["redes"]
    for i, a in enumerate(_actividades_del_programa(desde, hasta, anexo.REDES)):
        r = 7 + i
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", a["titulo"])
        x.escribir(h, f"C{r}", "Internacional" if a["ambito"] == "internacional" else "Nacional")
        x.escribir(h, f"D{r}", a["institucion"])
        x.escribir(h, f"F{r}", a["descripcion"])
        x.escribir(h, f"G{r}", _nombres(a["internos"]))
        x.escribir(h, f"H{r}", len(a["internos"]))


def _extension(x: Plantilla, desde: str, hasta: str):
    h = H["extension"]
    filas = []
    for p in _proyectos_del_programa(desde, hasta, "interaccion_social"):
        resp = [q for q in p["participantes"] if q["rol"] in ("responsable", "co_responsable")]
        filas.append((p["nombre"], p["objetivo_general"] or p["descripcion"], lineas.nombres(lineas.de_proyecto(p["id"])),
                      _nombres(resp), p["fecha_inicio"], p["fecha_fin"], len(p["internos"]), None))
    for a in _actividades_del_programa(desde, hasta, anexo.DIVULGACION):
        filas.append((a["titulo"], a["descripcion"], None, _nombres(a["internos"]), a["fecha_inicio"],
                      a["fecha_fin"] or a["fecha_inicio"], len(a["internos"]), a["tipo"]))
    filas.sort(key=lambda f: f[4] or "")
    for i, (nombre, desc, lin, resp, ini, fin, n, tipo) in enumerate(filas):
        r = 8 + i
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", nombre)
        x.escribir(h, f"C{r}", desc)
        x.escribir(h, f"D{r}", lin or None)
        x.escribir(h, f"E{r}", resp or None)
        x.escribir(h, f"F{r}", int(ini[:4]) if ini else None)
        x.escribir(h, f"G{r}", ini)
        x.escribir(h, f"H{r}", fin)
        x.escribir(h, f"I{r}", n)
        x.escribir(h, f"R{r}", tipo or "Proyecto de interacción social")


def _servicios(x: Plantilla, desde: str, hasta: str, tipo_cambio: float | None):
    h = H["servicios"]
    for i, a in enumerate(_actividades_del_programa(desde, hasta, anexo.SERVICIOS)):
        r = 8 + i
        partes = actividades.participantes(a["id"])
        anio = int(a["fecha_inicio"][:4])
        estudiantes_ = [p for p in partes if estudiantes.estudiante_de(p, anio)]
        monto = _usd(a["monto"], a["moneda"], tipo_cambio)
        ingresos = _usd(a["ingresos"], a["moneda"], tipo_cambio)
        x.escribir(h, f"A{r}", i + 1)
        x.escribir(h, f"B{r}", anio)
        x.escribir(h, f"C{r}", a["titulo"])
        x.escribir(h, f"D{r}", _nombres([p for p in partes if p["rol"] == "responsable"]) or _nombres(a["internos"]))
        x.escribir(h, f"E{r}", a["descripcion"])
        x.escribir(h, f"F{r}", a["institucion"])
        x.escribir(h, f"G{r}", len(a["internos"]))
        x.escribir(h, f"H{r}", len(estudiantes_))
        x.escribir(h, f"N{r}", monto if a["financiamiento"] == "interno" else None)
        x.escribir(h, f"O{r}", monto if a["financiamiento"] != "interno" else None)
        x.escribir(h, f"Q{r}", ingresos)
        obs = []
        if a["monto"] is not None and monto is None:
            obs.append(f"Monto: {a['monto']} {a['moneda'] or ''} (sin tipo de cambio a USD)".replace("  ", " "))
        if a["monto"] is not None and not a["financiamiento"]:
            obs.append("Origen del financiamiento sin indicar (se puso como externo)")
        x.escribir(h, f"R{r}", "; ".join(obs) or None)


# --- Generación ---------------------------------------------------------------------------------------

def generar(plan_id: int | None = None, ultimo: tuple[int, str] | None = None, tipo_cambio: float | None = None,
            plantilla: bytes | None = None) -> bytes:
    """La Guía del programa del plan `plan_id` (por omisión, el primer plan vigente de licenciatura)
    para los 10 ciclos que terminan en `ultimo` (por omisión, el último semestre que empezó).
    `tipo_cambio`: bolivianos por dólar, para los montos en USD (sin él, los montos en bolivianos
    quedan en blanco)."""
    ciclos = ciclos_hasta(*(ultimo or ultimo_ciclo_por_omision()))
    anio_ini, anio_fin = ciclos[0][0], ciclos[-1][0]
    desde, hasta = f"{anio_ini}-01-01", min(f"{anio_fin}-12-31", date.today().isoformat())
    x = Plantilla(plantilla or PLANTILLA.read_bytes())
    vigentes = planes_vigentes()
    plan = next((p for p in vigentes if p["id"] == plan_id), vigentes[0] if vigentes else None)
    _identificacion(x, plan, ciclos)
    _lineas(x, hasta)
    _cohortes(x, ciclos)
    _asignaturas(x, plan, anio_fin)
    _academicos(x, anio_ini, anio_fin, hasta)
    _caracterizacion(x, ciclos)
    _jefes_practica(x, anio_fin)
    _desarrollo(x, desde, hasta)
    _proyectos(x, desde, hasta, tipo_cambio)
    _profesional(x, desde, hasta)
    _articulos(x, anio_ini, anio_fin)
    _libros(x, anio_ini, anio_fin)
    _patentes(x, anio_ini, anio_fin)
    _redes(x, desde, hasta)
    _extension(x, desde, hasta)
    _servicios(x, desde, hasta, tipo_cambio)
    return x.guardar()
