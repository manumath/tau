"""Autoevaluación con el marco de calidad (PLAN §57, etapa 5): un proceso con periodo y estado, el juicio de cada criterio
en la escala del marco (con juicio fundado, fortalezas y debilidades), la síntesis de cada dimensión, el análisis global,
y su informe (imprimible y XLSX).

Mientras está en curso se registran juicios y síntesis; al concluirla quedan fijos (se puede reabrir). Las cifras de los
indicadores que muestra son las del tablero: los años cerrados están congelados; los abiertos se recalculan.
"""
from datetime import date

from app.calidad import evidencias, indicadores, marco
from app.comun import exportar
from app.comun.db import get_db, transaccion

ESTADOS = {"en_curso": "En curso", "concluida": "Concluida"}
LARGO_TEXTO = 10_000


# --- Lectura ------------------------------------------------------------------------------------------------

def listar(mid: int) -> list[dict]:
    filas = get_db().q(
        """SELECT a.*, (SELECT COUNT(*) FROM juicio_criterio j WHERE j.autoevaluacion_id = a.id AND j.nivel IS NOT NULL)
                       AS juzgados FROM autoevaluacion a WHERE a.marco_id = ? ORDER BY a.creada_en DESC, a.id DESC""",
        [mid])
    total = len(evidencias.criterios_del_marco(mid))
    for f in filas:
        f["criterios"] = total
    return filas


def obtener(aid: int) -> dict | None:
    f = get_db().q(
        """SELECT a.*, c.nombres || ' ' || c.apellidos AS concluida_por_nombre FROM autoevaluacion a
           LEFT JOIN usuario c ON c.id = a.concluida_por WHERE a.id = ?""", [aid])
    return f[0] if f else None


def en_curso(mid: int) -> dict | None:
    f = get_db().q("SELECT * FROM autoevaluacion WHERE marco_id = ? AND estado = 'en_curso'", [mid])
    return f[0] if f else None


def juicios(aid: int) -> dict[int, dict]:
    return {j["criterio_id"]: j for j in get_db().q(
        """SELECT j.*, u.nombres || ' ' || u.apellidos AS por FROM juicio_criterio j
           LEFT JOIN usuario u ON u.id = j.actualizado_por WHERE j.autoevaluacion_id = ?""", [aid])}


def sintesis(aid: int) -> dict[int, str]:
    return {f["dimension_id"]: f["sintesis"] for f in get_db().q(
        "SELECT dimension_id, sintesis FROM sintesis_dimension WHERE autoevaluacion_id = ?", [aid])}


def anios(a: dict) -> list[int]:
    return list(range(a["desde_anio"], a["hasta_anio"] + 1))


def arbol(a: dict, cifras: bool = False) -> list[dict]:
    """Dimensiones y criterios del marco con el juicio, las evidencias y (con `cifras`) los indicadores activos del
    criterio con sus cifras en los años del periodo."""
    js, sint = juicios(a["id"]), sintesis(a["id"])
    evs: dict[int, list] = {}
    for e in evidencias.listar(a["marco_id"]):
        for c in e["criterios"]:
            evs.setdefault(c["id"], []).append(e)
    tablero = indicadores.tablero(a["marco_id"], a["desde_anio"], a["hasta_anio"]) if cifras else None
    celdas = ({i["id"]: i["celdas"] for d in tablero["arbol"] for c in d["criterios"] for i in c["indicadores"]}
              if cifras else {})
    res = marco.arbol(a["marco_id"], inactivos=False)
    for d in res:
        d["sintesis"] = sint.get(d["id"])
        for c in d["criterios"]:
            c["juicio"] = js.get(c["id"])
            c["evidencias"] = evs.get(c["id"], [])
            for i in c["indicadores"]:
                i["celdas"] = celdas.get(i["id"], {})
    return res


def distribucion(arbol_: list[dict], escala: list[dict]) -> list[dict]:
    """Cuántos criterios hay en cada nivel, por dimensión y en total (con los sin juzgar)."""
    def cuenta(criterios):
        n = {x["valor"]: 0 for x in escala} | {None: 0}
        for c in criterios:
            n[c["juicio"]["nivel"] if c["juicio"] and c["juicio"]["nivel"] in n else None] += 1
        return n
    filas = [{"codigo": d["codigo"], "nombre": d["nombre"], "niveles": cuenta(d["criterios"])} for d in arbol_]
    filas.append({"codigo": "", "nombre": "Total", "niveles": cuenta([c for d in arbol_ for c in d["criterios"]])})
    return filas


def avance(a: dict) -> tuple[int, int]:
    """(criterios con nivel, criterios del marco)."""
    n = get_db().q("SELECT COUNT(*) n FROM juicio_criterio WHERE autoevaluacion_id = ? AND nivel IS NOT NULL",
                   [a["id"]])[0]["n"]
    return n, len(evidencias.criterios_del_marco(a["marco_id"]))


def concluida_en_ventana(mid: int, anio: int, ventana: int = 5) -> dict | None:
    """La autoevaluación más reciente concluida en los `ventana` años que terminan en `anio`."""
    f = get_db().q(
        """SELECT * FROM autoevaluacion WHERE marco_id = ? AND estado = 'concluida'
             AND CAST(substr(concluida_en, 1, 4) AS INTEGER) BETWEEN ? AND ? ORDER BY concluida_en DESC LIMIT 1""",
        [mid, anio - ventana + 1, anio])
    return f[0] if f else None


# --- Validación y escritura -------------------------------------------------------------------------------------

def _texto(v) -> str | None:
    return (v or "").strip()[:LARGO_TEXTO] or None


def validar(d: dict) -> tuple[dict, list[str]]:
    errores = []
    x = {"nombre": (d.get("nombre") or "").strip(), "desde_anio": (d.get("desde_anio") or "").strip(),
         "hasta_anio": (d.get("hasta_anio") or "").strip()}
    if not x["nombre"]:
        errores.append("Indique el nombre de la autoevaluación.")
    try:
        x["desde_anio"], x["hasta_anio"] = int(x["desde_anio"]), int(x["hasta_anio"])
        if not (2000 <= x["desde_anio"] <= x["hasta_anio"] <= date.today().year):
            raise ValueError
    except ValueError:
        errores.append(f"El periodo evaluado va de un año a otro, entre 2000 y {date.today().year}.")
    return x, errores


def crear(mid: int, x: dict, uid: int) -> int | None:
    """None si ya hay una en curso."""
    if en_curso(mid):
        return None
    return get_db().t.autoevaluacion.insert(marco_id=mid, creada_por=uid, **x)["id"]


def actualizar(aid: int, x: dict):
    get_db().t.autoevaluacion.update(x, aid)


def validar_juicio(d: dict, escala: list[dict]) -> tuple[dict, list[str]]:
    niveles = {str(n["valor"]): n for n in escala}
    x = {k: _texto(d.get(k)) for k in ("juicio", "fortalezas", "debilidades")}
    nivel = (d.get("nivel") or "").strip()
    errores = []
    if nivel and nivel not in niveles:
        errores.append("Elija un nivel de la escala.")
        nivel = ""
    x["nivel"] = int(nivel) if nivel else None
    x["nivel_nombre"] = niveles[nivel]["nombre"] if nivel else None
    if x["nivel"] is not None and not x["juicio"]:
        errores.append("Fundamente el nivel en el juicio.")
    return x, errores


def guardar_juicio(aid: int, cid: int, x: dict, uid: int):
    get_db().execute(
        """INSERT INTO juicio_criterio (autoevaluacion_id, criterio_id, nivel, nivel_nombre, juicio, fortalezas,
                                        debilidades, actualizado_por) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (autoevaluacion_id, criterio_id) DO UPDATE SET nivel = excluded.nivel,
             nivel_nombre = excluded.nivel_nombre, juicio = excluded.juicio, fortalezas = excluded.fortalezas,
             debilidades = excluded.debilidades, actualizado_por = excluded.actualizado_por,
             actualizado_en = datetime('now')""",
        [aid, cid, x["nivel"], x["nivel_nombre"], x["juicio"], x["fortalezas"], x["debilidades"], uid])


def guardar_sintesis(aid: int, did: int, texto: str, uid: int):
    texto = _texto(texto)
    if not texto:
        get_db().execute("DELETE FROM sintesis_dimension WHERE autoevaluacion_id = ? AND dimension_id = ?", [aid, did])
        return
    get_db().execute(
        """INSERT INTO sintesis_dimension (autoevaluacion_id, dimension_id, sintesis, actualizado_por) VALUES (?, ?, ?, ?)
           ON CONFLICT (autoevaluacion_id, dimension_id) DO UPDATE SET sintesis = excluded.sintesis,
             actualizado_por = excluded.actualizado_por, actualizado_en = datetime('now')""", [aid, did, texto, uid])


def guardar_analisis(aid: int, texto: str):
    get_db().t.autoevaluacion.update({"analisis_global": _texto(texto)}, aid)


def faltantes(a: dict) -> list[dict]:
    """Criterios del marco sin nivel (impiden concluir)."""
    js = juicios(a["id"])
    return [c for c in evidencias.criterios_del_marco(a["marco_id"])
            if not (js.get(c["id"]) and js[c["id"]]["nivel"] is not None)]


def concluir(a: dict, uid: int) -> list[str]:
    """Concluye si todos los criterios tienen nivel; devuelve los errores."""
    if a["estado"] != "en_curso":
        return ["La autoevaluación ya está concluida."]
    falta = faltantes(a)
    if falta:
        return [f"Faltan {len(falta)} criterios por juzgar: " + ", ".join(c["codigo"] for c in falta[:10])
                + ("…" if len(falta) > 10 else "") + "."]
    get_db().execute("""UPDATE autoevaluacion SET estado = 'concluida', concluida_por = ?, concluida_en = datetime('now')
                        WHERE id = ?""", [uid, a["id"]])
    return []


def reabrir(a: dict) -> list[str]:
    if a["estado"] != "concluida":
        return ["La autoevaluación no está concluida."]
    otra = en_curso(a["marco_id"])
    if otra:
        return [f"Ya hay otra autoevaluación en curso («{otra['nombre']}»)."]
    get_db().execute("""UPDATE autoevaluacion SET estado = 'en_curso', concluida_por = NULL, concluida_en = NULL
                        WHERE id = ?""", [a["id"]])
    return []


def eliminar(a: dict) -> bool:
    """Solo una en curso (una concluida es historia)."""
    if a["estado"] != "en_curso":
        return False
    with transaccion():
        get_db().execute("DELETE FROM autoevaluacion WHERE id = ?", [a["id"]])
    return True


# --- Exportación ----------------------------------------------------------------------------------------------

def a_xlsx(a: dict) -> bytes:
    escala = marco.escala(a["marco_id"])
    ar = arbol(a, cifras=True)
    periodo = anios(a)
    juicios_ = [{"dimension": d["codigo"], "criterio": c["codigo"], "nombre": c["nombre"],
                 "nivel": c["juicio"]["nivel"] if c["juicio"] and c["juicio"]["nivel"] is not None else "",
                 "nivel_nombre": (c["juicio"] or {}).get("nivel_nombre") or "",
                 "juicio": (c["juicio"] or {}).get("juicio") or "",
                 "fortalezas": (c["juicio"] or {}).get("fortalezas") or "",
                 "debilidades": (c["juicio"] or {}).get("debilidades") or "",
                 "evidencias": len(c["evidencias"])} for d in ar for c in d["criterios"]]
    dims = [{"dimension": d["codigo"], "nombre": d["nombre"], "sintesis": d["sintesis"] or "",
             **{n["nombre"]: x["niveles"][n["valor"]] for n in escala}, "sin juzgar": x["niveles"][None]}
            for d, x in zip(ar, distribucion(ar, escala), strict=False)]
    inds = []
    for d in ar:
        for c in d["criterios"]:
            for i in c["indicadores"]:
                f = {"criterio": c["codigo"], "codigo": i["codigo"], "indicador": i["nombre"],
                     "unidad": i["unidad_medida"] or ""}
                for y in periodo:
                    x = i["celdas"].get(y) or {}
                    f[str(y)] = "" if x.get("valor") is None else x["valor"]
                    f[f"meta {y}"] = "" if x.get("meta") is None else x["meta"]
                inds.append(f)
    evs = [{"criterio": c["codigo"], "evidencia": e["titulo"], "tipo": evidencias.TIPOS[e["tipo"]],
            "fecha": e["fecha"] or "", "vigente_hasta": e["vigente_hasta"] or "", "sha256": e["sha256"] or "",
            "enlace": e["url"] or ""} for d in ar for c in d["criterios"] for e in c["evidencias"]]
    datos = [{"campo": k, "valor": v} for k, v in (
        ("Autoevaluación", a["nombre"]), ("Periodo evaluado", f"{a['desde_anio']}–{a['hasta_anio']}"),
        ("Estado", ESTADOS[a["estado"]]), ("Concluida", a["concluida_en"] or ""),
        ("Análisis global", a["analisis_global"] or ""))]
    return exportar.a_xlsx({"Autoevaluación": datos, "Juicios": juicios_, "Dimensiones": dims, "Indicadores": inds,
                            "Evidencias": evs,
                            "Escala": [{"valor": n["valor"], "nivel": n["nombre"], "descripcion": n["descripcion"] or ""}
                                       for n in escala]})
