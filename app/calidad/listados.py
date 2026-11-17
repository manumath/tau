"""Listados de la ficha estadística (PLAN §61): tablas de una fila por persona, asignatura, capacitación, producto,
proyecto o actividad, para llenar los formularios de antecedentes que las piden así (además de las cifras sueltas de
`ficha.valores`).

Cada listado tiene columnas con clave estable. En `ficha.valores` cada columna es la clave `listado.<tabla>.<columna>`
y su valor es la lista de la columna, en el orden de las filas: una correspondencia la escribe hacia abajo desde la
celda indicada. Como en el resto de la ficha, **no hay datos personales sensibles**: ni fecha de nacimiento ni edad (los
tramos de edad van en las cifras), ni correos.
"""
from app.academico import gestiones, planes
from app.calidad import capacitacion
from app.informes import anexo, informes
from app.informes import estudiantes as ind_estudiantes
from app.comun import academicos, adscripcion, vinculos
from app.comun.db import get_db
from app.investigacion import actividades, lineas, proyectos

# tabla → {columna: descripción}. El orden de las columnas es el de la hoja «Listados» del XLSX de la ficha.
COLUMNAS = {
    "academicos": {
        "apellidos": "Apellidos", "nombres": "Nombres",
        "grado_1": "Grado 1 (el primero)", "institucion_1": "Institución del grado 1",
        "grado_2": "Grado 2", "institucion_2": "Institución del grado 2",
        "grado_3": "Grado 3", "institucion_3": "Institución del grado 3",
        "anio_incorporacion": "Año de incorporación", "fecha_ingreso": "Fecha de ingreso (DD/MM/AAAA)",
        "unidad": "Unidad o grupo", "cargo": "Cargo", "categoria": "Categoría",
        "horas_docencia": "Horas de docencia (h/mes)", "horas_investigacion": "Horas de investigación (h/mes)",
        "horas_extension": "Horas de extensión y servicios (h/mes)", "horas_gestion": "Horas de gestión (h/mes)",
        "horas_otras": "Otras horas (h/mes)", "horas_extension_y_otras": "Extensión y otras (h/mes)",
        "horas_total": "Carga contratada (h/mes)", "n_cursos": "N.º de asignaturas dictadas como titular",
        "cursos": "Asignaturas dictadas (gestiones)", "n_tesis": "N.º de tesis dirigidas defendidas",
        "tesis": "Tesis dirigidas defendidas",
    },
    "capacitacion": {
        "anio": "Año en que concluyó", "apellidos": "Apellidos", "nombres": "Nombres", "titulo": "Capacitación",
        "institucion": "Institución", "area": "Área", "horas": "Horas",
    },
    "articulos": {
        "anio": "Año", "titulo": "Título", "autores_internos": "Autores del programa", "autores_externos": "Autores externos",
        "lineas": "Líneas de investigación", "proyectos": "Proyectos", "tipo": "Tipo", "medio": "Revista o actas",
        "ambito": "Ámbito de la revista", "indices": "Indexación", "estado": "Estado", "issn": "ISSN", "doi": "DOI",
        "url": "Enlace",
    },
    "libros": {
        "anio": "Año", "tipo": "Tipo", "titulo": "Título", "autores": "Autores", "lineas": "Líneas de investigación",
        "medio": "Libro o editorial", "revision": "Revisión", "estado": "Estado", "doi": "DOI", "url": "Enlace",
    },
    "proyectos": {
        "anio_inicio": "Año de inicio", "anio_fin": "Año de término", "meses": "Duración (meses)", "nombre": "Nombre",
        "tipo": "Tipo", "resumen": "Resumen", "lineas": "Líneas de investigación", "responsables": "Responsables",
        "participantes": "Participantes internos", "n_participantes": "N.º de participantes internos",
        "externos": "Participantes externos", "n_externos": "N.º de participantes externos",
        "fuente": "Fuente de financiamiento", "monto": "Monto", "moneda": "Moneda",
    },
    "actividades": {
        "tipo": "Tipo", "titulo": "Nombre", "anio": "Año", "inicio": "Inicio", "fin": "Término", "lugar": "Ciudad",
        "pais": "País", "institucion": "Institución", "ambito": "Ámbito", "modalidad": "Modalidad",
        "participantes": "Participantes (rol)", "n_participantes": "N.º de participantes del programa",
        "descripcion": "Descripción", "monto": "Monto", "moneda": "Moneda",
    },
}
# Columnas de los listados de cada plan de estudios: asignaturas (con su semestre) y electivas.
COLUMNAS_PLAN = {
    "semestre": "Semestre o ciclo", "nombre": "Asignatura (sigla)", "sigla": "Sigla", "tipo": "Tipo",
    "tiene_requisitos": "¿Tiene requisitos? (sí/no)", "requisitos": "Requisitos", "veces_dictada": "Veces que se dictó",
    "max_estudiantes": "Máximo de estudiantes por paralelo", "linea_formativa": "Línea formativa",
    "area_o_linea": "Área o línea de investigación", "horas": "Horas semanales (T + P + L)", "creditos": "Créditos",
}
ARTICULOS = ("Artículo en revista", "Artículo en actas de congreso")
LIBROS = ("Libro", "Capítulo de libro")
SEPARADOR = "; "


def _fecha(iso: str | None) -> str | None:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso and len(iso) >= 10 else iso


def _nombre(p: dict) -> str:
    return f"{p['apellidos']}, {p['nombres']}"


def _ordinal(n: int) -> str:
    return f"{n}.{'er' if n in (1, 3) else 'º'} semestre"


# --- Académicos -------------------------------------------------------------------------------------------------------

def _cursos(uid: int, desde: int, hasta: int) -> list[str]:
    """«Álgebra I (I-2023, I-2024)» por asignatura que dictó como titular en el periodo."""
    filas = get_db().q(
        """SELECT a.nombre, g.anio, g.tipo FROM oferta_docente od JOIN oferta o ON o.id = od.oferta_id
           JOIN asignatura a ON a.id = o.asignatura_id JOIN gestion_academica g ON g.id = o.gestion_id
           WHERE od.usuario_id = ? AND od.rol = 'titular' AND g.anio BETWEEN ? AND ?
           ORDER BY a.nombre, g.anio, g.tipo""", [uid, desde, hasta])
    por = {}
    for f in filas:
        codigo = gestiones.codigo(f)
        if codigo not in por.setdefault(f["nombre"], []):
            por[f["nombre"]].append(codigo)
    return [f"{n} ({', '.join(g)})" for n, g in por.items()]


def academicos_(anios: list[int], hasta: str) -> list[dict]:
    """Personas vinculadas al cierre del último año de la ventana, con lo que hicieron en toda la ventana."""
    a0, a1 = anios[0], anios[-1]
    cuerpo = anexo.cuerpo_academico(a1, hasta)
    tesis = ind_estudiantes.tesis(a0, a1)
    res = []
    for p in sorted(cuerpo["personas"], key=lambda x: (x["apellidos"], x["nombres"])):
        uid = p["id"]
        gs = sorted(academicos.grados(uid), key=lambda g: -academicos.NIVELES[g["nivel"]][1])[:3]
        hist = [v for v in vinculos.listar(uid) if v["fecha_inicio"]]
        ingreso = min((v["fecha_inicio"] for v in hist), default=None)
        c = vinculos.carga_de(vinculos.vigente(uid, cuerpo["corte"])) or {"horas": None, "actividades": {}}
        act = c["actividades"]
        cursos = _cursos(uid, a0, a1)
        dirigidas = [t["producto"]["titulo"] for t in tesis
                     if t["estado"] == "defendida" and any(d["id"] == uid for d in t["directores"])]
        fila = {"apellidos": p["apellidos"], "nombres": p["nombres"],
                "anio_incorporacion": int(ingreso[:4]) if ingreso else None, "fecha_ingreso": _fecha(ingreso),
                "unidad": adscripcion.unidad(uid), "cargo": adscripcion.cargo(uid), "categoria": p["categoria"],
                **{f"horas_{k}": act.get(k) for k in vinculos.ACTIVIDADES},
                "horas_extension_y_otras": (act.get("extension") or 0) + (act.get("otras") or 0) if act else None,
                "horas_total": c["horas"], "n_cursos": len(cursos), "cursos": SEPARADOR.join(cursos) or None,
                "n_tesis": len(dirigidas), "tesis": SEPARADOR.join(dirigidas) or None}
        for i in range(3):
            g = gs[i] if i < len(gs) else None
            fila[f"grado_{i + 1}"] = (g["titulo"] or academicos.NIVELES[g["nivel"]][0]) if g else None
            fila[f"institucion_{i + 1}"] = (f"{g['institucion']} ({g['pais']})" if g and g["institucion"] and g["pais"]
                                            else g["institucion"] if g else None)
        res.append(fila)
    return res


# --- Plan de estudios -------------------------------------------------------------------------------------------------

def _dictado(desde: int, hasta: int) -> dict[int, dict]:
    """asignatura → {veces: gestiones en que se ofreció, max: máximo de inscritos en un paralelo}."""
    return {f["asignatura_id"]: {"veces": f["veces"], "max": f["max"]} for f in get_db().q(
        """SELECT o.asignatura_id, COUNT(DISTINCT o.gestion_id) AS veces, MAX(o.inscritos) AS max
           FROM oferta o JOIN gestion_academica g ON g.id = o.gestion_id
           WHERE g.anio BETWEEN ? AND ? AND o.retirada_en IS NULL GROUP BY o.asignatura_id""", [desde, hasta])}


def _fila_plan(f: dict, dictado: dict, semestre: str) -> dict:
    d = dictado.get(f["asignatura_id"]) or {}
    nombre = f"{f['nombre']} ({f['sigla']})" if f["asignatura_id"] else planes.TIPOS[f["tipo"]]
    horas = [f[k] for k in ("horas_teoricas", "horas_practicas", "horas_laboratorio") if f.get(k)]
    return {"semestre": semestre, "nombre": nombre, "sigla": f["sigla"], "tipo": planes.TIPOS[f["tipo"]],
            "tiene_requisitos": ("sí" if f["requisitos"] else "no") if f["asignatura_id"] else None,
            "requisitos": ", ".join(f["requisitos"]) or None, "veces_dictada": d.get("veces"),
            "max_estudiantes": d.get("max"), "linea_formativa": f.get("linea_formativa"),
            "area_o_linea": f.get("linea") or (f"Área de {f['area']}" if f.get("area") else None),
            "horas": sum(horas) if horas else None, "creditos": f.get("creditos")}


def plan_(pid: int, desde: int, hasta: int) -> tuple[list[dict], list[dict]]:
    """(asignaturas y casillas por semestre, electivas) de un plan, con lo dictado en el periodo."""
    dictado = _dictado(desde, hasta)
    filas = [_fila_plan(f, dictado, f"{_ordinal(s)}" + (f" (ciclo {c})" if c else ""))
             for s, c, fs in planes.por_semestre(pid) for f in fs]
    electivas = [_fila_plan(f, dictado, planes.GRUPOS_ELECTIVAS[g])
                 for g, fs in planes.electivas(pid).items() for f in fs]
    return filas, electivas


def clave_plan(p: dict) -> str:
    """«licenciatura_en_matematica_plan_2017»: la clave de un plan en los listados."""
    from app.calidad.ficha import _slug
    return _slug(f"{p['programa']} {p['nombre']}")


# --- Producción ---------------------------------------------------------------------------------------------------

def _lineas(registros: list[dict]) -> str | None:
    return SEPARADOR.join(dict.fromkeys(x["nombre"] for x in registros)) or None


def _proyectos_de(pid: int) -> str | None:
    return SEPARADOR.join(x["nombre"] for x in get_db().q(
        """SELECT p.nombre FROM producto_proyecto pp JOIN proyecto p ON p.id = pp.proyecto_id
           WHERE pp.producto_id = ? AND pp.estado = 'aprobado' ORDER BY p.nombre""", [pid])) or None


def _autores(p: dict, internos: bool | None = None) -> str | None:
    return SEPARADOR.join(_nombre(a) for a in p["autores"] if internos is None or bool(a.get("interno")) == internos) or None


def produccion(desde: int, hasta: int) -> dict[str, list[dict]]:
    """Artículos, libros, proyectos y actividades que cuentan en la memoria del periodo."""
    m = informes.memoria(desde=f"{desde}-01-01", hasta=f"{hasta}-12-31", exigir_verificada=False)
    articulos, libros = [], []
    for p in sorted(m["productos"], key=lambda x: (-x["anio"], x["titulo"])):
        comun = {"anio": p["anio"], "titulo": p["titulo"], "lineas": _lineas(lineas.de_registro("producto", p["id"])),
                 "tipo": p["tipo"], "medio": p.get("medio"), "estado": p.get("estado_publicacion"),
                 "doi": p.get("doi"), "url": p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else None)}
        if p["tipo"] in ARTICULOS:
            rev = p.get("revista") or {}
            articulos.append({**comun, "autores_internos": _autores(p, True), "autores_externos": _autores(p, False),
                              "proyectos": _proyectos_de(p["id"]),
                              "ambito": (p.get("detalle_revista") or {}).get("ambito"),
                              "indices": SEPARADOR.join(i["nombre"] for i in p.get("indices") or []) or None,
                              "issn": rev.get("issn") or rev.get("eissn")})
        elif p["tipo"] in LIBROS:
            libros.append({**comun, "autores": _autores(p), "revision": p.get("revision")})
    proys = []
    for p in sorted(m["proyectos"], key=lambda x: (x["fecha_inicio"] or "", x["nombre"])):
        parts = proyectos.participantes(p["id"])
        internos = [x for x in parts if x.get("interno")]
        externos = [x for x in parts if not x.get("interno")]
        ini, fin = p["fecha_inicio"], p["fecha_fin"]
        meses = ((int(fin[:4]) - int(ini[:4])) * 12 + int(fin[5:7]) - int(ini[5:7]) + 1) if ini and fin else None
        proys.append({"anio_inicio": int(ini[:4]) if ini else None, "anio_fin": int(fin[:4]) if fin else None,
                      "meses": meses, "nombre": p["nombre"], "tipo": proyectos.tipo_texto(p),
                      "resumen": p.get("descripcion"), "lineas": _lineas(lineas.de_proyecto(p["id"])),
                      "responsables": SEPARADOR.join(_nombre(x) for x in parts
                                                     if x["rol"] in ("responsable", "co_responsable")) or None,
                      "participantes": SEPARADOR.join(_nombre(x) for x in internos) or None,
                      "n_participantes": len(internos),
                      "externos": SEPARADOR.join(_nombre(x) + (f" ({x['afiliacion']})" if x.get("afiliacion") else "")
                                                 for x in externos) or None,
                      "n_externos": len(externos), "fuente": p.get("fuente_financiamiento"), "monto": p.get("monto"),
                      "moneda": p.get("moneda")})
    acts = []
    for a in sorted(m["actividades"], key=lambda x: (x["tipo"], x["fecha_inicio"])):
        parts = actividades.participantes(a["id"])
        acts.append({"tipo": a["tipo"], "titulo": a["titulo"], "anio": int(a["fecha_inicio"][:4]),
                     "inicio": _fecha(a["fecha_inicio"]), "fin": _fecha(a["fecha_fin"]), "lugar": a.get("lugar"),
                     "pais": a.get("pais"), "institucion": a.get("institucion"),
                     "ambito": actividades.AMBITOS.get(a.get("ambito")),
                     "modalidad": actividades.MODALIDADES.get(a.get("modalidad")),
                     "participantes": SEPARADOR.join(f"{_nombre(x)} ({actividades.ROLES.get(x['rol'], x['rol'])})"
                                                     for x in parts) or None,
                     "n_participantes": sum(1 for x in parts if x.get("interno")),
                     "descripcion": a.get("descripcion"), "monto": a.get("monto"), "moneda": a.get("moneda")})
    return {"articulos": articulos, "libros": libros, "proyectos": proys, "actividades": acts}


def capacitacion_(desde: int, hasta: int) -> list[dict]:
    res = []
    for a in range(desde, hasta + 1):
        for c in capacitacion.listar(a):
            res.append({"anio": a, "apellidos": c["apellidos"], "nombres": c["nombres"], "titulo": c["titulo"],
                        "institucion": c["institucion"], "area": capacitacion.AREAS[c["area"]], "horas": c["horas"]})
    return sorted(res, key=lambda x: (x["anio"], x["apellidos"], x["nombres"]))


# --- Todo junto --------------------------------------------------------------------------------------------------

def todos(anios: list[int], hasta: str) -> dict[str, tuple[dict, list[dict]]]:
    """tabla → (columnas, filas) de todos los listados de la ventana `anios`."""
    a0, a1 = anios[0], anios[-1]
    res = {"academicos": (COLUMNAS["academicos"], academicos_(anios, hasta)),
           "capacitacion": (COLUMNAS["capacitacion"], capacitacion_(a0, a1))}
    for p in planes.listar():
        filas, electivas = plan_(p["id"], a0, a1)
        res[f"asignaturas_{clave_plan(p)}"] = (COLUMNAS_PLAN, filas)
        if electivas:
            res[f"electivas_{clave_plan(p)}"] = (COLUMNAS_PLAN, electivas)
    for k, filas in produccion(a0, a1).items():
        res[k] = (COLUMNAS[k], filas)
    return res


def valores(listados: dict) -> dict[str, list]:
    """`listado.<tabla>.<columna>` → la columna como lista."""
    return {f"listado.{t}.{c}": [f.get(c) for f in filas] for t, (cols, filas) in listados.items() for c in cols}
