"""Informes de docencia (PLAN.md, sección 29): carga docente por semestre e indicadores del cuerpo
académico por año, como los pide IAC-CINDA.

- **Carga docente** (un semestre): por persona, la carga contratada y su distribución, la JCE
  (carga / 160), la docencia prevista frente a la asignada, la carga en proyectos y los avisos; por
  categoría y en total; y las inscripciones del semestre por JCE.
- **Indicadores** (por año, al 31 de diciembre o a hoy): académicos vinculados y JCE (los de
  `anexo.cuerpo_academico`), porcentaje con doctorado y con posgrado, distribución por categoría y
  por tramo de edad (nunca la fecha de nacimiento), porcentaje de la carga dedicada a investigación,
  porcentaje con proyecto vigente e inscripciones por JCE en el segundo semestre del año (o el
  primero, si aún no hay segundo).

Las «inscripciones» son la suma de inscritos por paralelo de la oferta: una persona que cursa dos
materias cuenta dos veces. No es la matrícula de la Carrera (esa la entrega el sistema académico
de la UMSA).
"""
from datetime import date

from app.academico import carga, gestiones
from app.acreditacion import anexo
from app.comun import academicos, vinculos
from app.comun.db import get_db

JORNADA_COMPLETA = anexo.JORNADA_COMPLETA
ACTIVIDADES_NO_DOCENCIA = ("investigacion", "extension", "gestion", "otras")


def _pct(parte, total) -> float | None:
    return round(100 * parte / total, 1) if total else None


def _jce(horas) -> float:
    return round((horas or 0) / JORNADA_COMPLETA, 2)


# --- Carga docente de un semestre ------------------------------------------------------------------

def inscripciones(gestion_id: int) -> dict:
    fila = get_db().q(
        """SELECT COUNT(*) AS paralelos, COALESCE(SUM(inscritos), 0) AS inscritos,
                  SUM(inscritos IS NULL) AS sin_dato,
                  SUM(NOT EXISTS (SELECT 1 FROM oferta_docente d WHERE d.oferta_id = o.id AND d.rol = 'titular'))
                      AS sin_docente
           FROM oferta o WHERE o.gestion_id = ?""", [gestion_id])[0]
    return {k: fila[k] or 0 for k in ("paralelos", "inscritos", "sin_dato", "sin_docente")}


def carga_docente(gestion: dict) -> dict:
    filas, por_categoria = [], {}
    for r in carga.personas(gestion):
        v, c = r["vinculo"], r["carga"]
        acts = c["actividades"] if c else {k: 0 for k in vinculos.ACTIVIDADES}
        en_proyectos = carga.en_proyectos(v["id"]) if v else []
        fila = {
            "id": r["id"], "nombre": f"{r['apellidos']}, {r['nombres']}",
            "categoria": vinculos.CATEGORIAS[v["categoria"]] if v else "Sin vínculo",
            "contratada": r["contratada"], "jce": _jce(r["contratada"]),
            "prevista": r["prevista"], "asignada": r["asignada"], "materias": len(r["materias"]),
            **{k: acts[k] for k in ACTIVIDADES_NO_DOCENCIA},
            "inv_proyectos": sum(x["horas"] for x in en_proyectos if x["clase"] == "investigacion"),
            "ext_proyectos": sum(x["horas"] for x in en_proyectos if x["clase"] == "interaccion_social"),
            "avisos": r["avisos"],
        }
        filas.append(fila)
        cat = por_categoria.setdefault(fila["categoria"], {"personas": 0, "horas": 0, "docencia": 0,
                                                            **{k: 0 for k in ACTIVIDADES_NO_DOCENCIA}})
        cat["personas"] += 1
        cat["horas"] += fila["contratada"] or 0
        cat["docencia"] += fila["asignada"]
        for k in ACTIVIDADES_NO_DOCENCIA:
            cat[k] += fila[k]
    for cat in por_categoria.values():
        cat["jce"] = _jce(cat["horas"])
    horas = sum(f["contratada"] or 0 for f in filas)
    total = {"personas": len(filas), "horas": horas, "jce": _jce(horas),
             "docencia": sum(f["asignada"] for f in filas), "prevista": sum(f["prevista"] or 0 for f in filas),
             **{k: sum(f[k] for f in filas) for k in ACTIVIDADES_NO_DOCENCIA},
             "con_avisos": sum(bool(f["avisos"]) for f in filas)}
    total["pct_investigacion"] = _pct(total["investigacion"], horas)
    insc = inscripciones(gestion["id"])
    return {"gestion": gestion, "filas": filas, "por_categoria": por_categoria, "total": total,
            "inscripciones": insc,
            "inscripciones_por_jce": round(insc["inscritos"] / total["jce"], 1) if total["jce"] else None}


def filas_xlsx(datos: dict) -> dict[str, list[dict]]:
    act = vinculos.ACTIVIDADES
    personas = [{"Persona": f["nombre"], "Categoría": f["categoria"], "Contratada (h/mes)": f["contratada"] or "",
                 "JCE": f["jce"], "Docencia prevista": f["prevista"] if f["prevista"] is not None else "",
                 "Docencia asignada": f["asignada"], "Materias": f["materias"],
                 **{act[k]: f[k] for k in ACTIVIDADES_NO_DOCENCIA},
                 "Investigación en proyectos": f["inv_proyectos"], "Extensión en proyectos": f["ext_proyectos"],
                 "Avisos": " ".join(f["avisos"])} for f in datos["filas"]]
    categorias = [{"Categoría": c, "Personas": x["personas"], "Horas contratadas": x["horas"], "JCE": x["jce"],
                   "Docencia asignada": x["docencia"], **{act[k]: x[k] for k in ACTIVIDADES_NO_DOCENCIA}}
                  for c, x in datos["por_categoria"].items()]
    i = datos["inscripciones"]
    resumen = [{"Indicador": k, "Valor": v} for k, v in (
        ("Personas", datos["total"]["personas"]), ("Horas contratadas (h/mes)", datos["total"]["horas"]),
        ("Jornadas completas equivalentes", datos["total"]["jce"]),
        ("Porcentaje de la carga en investigación", datos["total"]["pct_investigacion"] or ""),
        ("Paralelos", i["paralelos"]), ("Paralelos sin docente titular", i["sin_docente"]),
        ("Inscripciones", i["inscritos"]), ("Inscripciones por JCE", datos["inscripciones_por_jce"] or ""))]
    return {"Resumen": resumen, "Por persona": personas, "Por categoría": categorias}


# --- Indicadores del cuerpo académico por año --------------------------------------------------------

def _grado_hasta(uid: int, anio: int) -> str | None:
    """Nivel del grado más alto obtenido hasta el año (los grados sin año cuentan siempre)."""
    niveles = [g["nivel"] for g in academicos.grados(uid) if not g["anio"] or g["anio"] <= anio]
    orden = {k: v[1] for k, v in academicos.NIVELES.items()}
    return min(niveles, key=lambda n: orden[n]) if niveles else None


def _con_proyecto(uid: int, fecha: str) -> bool:
    return bool(get_db().q(
        """SELECT 1 FROM proyecto_participante pp JOIN proyecto p ON p.id = pp.proyecto_id
           WHERE pp.investigador_id = :u AND p.estado != 'formulacion'
             AND COALESCE(p.fecha_inicio, '0000-01-01') <= :f AND COALESCE(p.fecha_fin, '9999-12-31') >= :f
             AND COALESCE(pp.fecha_desde, '0000-01-01') <= :f AND COALESCE(pp.fecha_hasta, '9999-12-31') >= :f
           LIMIT 1""", {"u": uid, "f": fecha}))


def _semestre_del_anio(anio: int, corte: str) -> dict | None:
    """El II del año si ya empezó al corte; si no, el I."""
    for tipo in ("II", "I"):
        g = gestiones.por_codigo(f"{tipo}-{anio}")
        if g and g["fecha_inicio"] <= corte:
            return g
    return None


def indicadores_anio(anio: int, hasta: str | None = None) -> dict:
    cuerpo = anexo.cuerpo_academico(anio, hasta or date.today().isoformat())
    corte, personas = cuerpo["corte"], cuerpo["personas"]
    grados = [_grado_hasta(p["id"], anio) for p in personas]
    tramos = {nombre: 0 for _, _, nombre in academicos.TRAMOS_EDAD}
    tramos["Sin dato"] = 0
    horas_inv = horas_con_carga = 0
    for p in personas:
        tramos[academicos.tramo_edad(p["id"], corte) or "Sin dato"] += 1
        c = vinculos.carga_de(vinculos.vigente(p["id"], corte))
        if c:
            horas_con_carga += c["horas"]
            horas_inv += c["actividades"]["investigacion"]
    con_proyecto = sum(_con_proyecto(p["id"], corte) for p in personas)
    semestre = _semestre_del_anio(anio, corte)
    insc = inscripciones(semestre["id"])["inscritos"] if semestre else None
    n = cuerpo["total"]
    return {
        "anio": anio, "corte": corte, "total": n, "jce": cuerpo["jce"], "sin_jornada": cuerpo["sin_jornada"],
        "por_categoria": cuerpo["por_categoria"],
        "doctores": grados.count("doctorado"), "pct_doctores": _pct(grados.count("doctorado"), n),
        "posgrado": sum(g in ("doctorado", "maestria") for g in grados),
        "pct_posgrado": _pct(sum(g in ("doctorado", "maestria") for g in grados), n),
        "sin_grado": grados.count(None),
        "tramos": tramos,
        "pct_investigacion": _pct(horas_inv, horas_con_carga),
        "con_proyecto": con_proyecto, "pct_con_proyecto": _pct(con_proyecto, n),
        "semestre": gestiones.codigo(semestre) if semestre else None, "inscripciones": insc,
        "inscripciones_por_jce": round(insc / cuerpo["jce"], 1) if insc and cuerpo["jce"] else None,
    }


def indicadores(desde_anio: int, hasta_anio: int) -> list[dict]:
    return [indicadores_anio(a) for a in range(desde_anio, hasta_anio + 1)]


def filas_indicadores(serie: list[dict]) -> dict[str, list[dict]]:
    principales = [{"Año": x["anio"], "Al": x["corte"], "Académicos vinculados": x["total"], "JCE": x["jce"],
                    "Con doctorado (%)": x["pct_doctores"] if x["pct_doctores"] is not None else "",
                    "Con posgrado (%)": x["pct_posgrado"] if x["pct_posgrado"] is not None else "",
                    "Sin grado registrado": x["sin_grado"],
                    "Carga en investigación (%)": x["pct_investigacion"] if x["pct_investigacion"] is not None else "",
                    "Con proyecto vigente (%)": x["pct_con_proyecto"] if x["pct_con_proyecto"] is not None else "",
                    "Semestre de referencia": x["semestre"] or "",
                    "Inscripciones por JCE": x["inscripciones_por_jce"] or ""} for x in serie]
    categorias = sorted({c for x in serie for c in x["por_categoria"]})
    por_categoria = [{"Año": x["anio"], **{c: x["por_categoria"].get(c, 0) for c in categorias}} for x in serie]
    por_edad = [{"Año": x["anio"], **x["tramos"]} for x in serie]
    return {"Indicadores": principales, "Por categoría": por_categoria, "Por tramo de edad": por_edad}
