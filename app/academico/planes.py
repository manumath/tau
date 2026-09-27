"""Consultas de los planes de estudio (catálogo curricular, PLAN.md sección 24)."""
from app.academico import importar_planes
from app.comun.db import AHORA, get_db

NIVELES = {"licenciatura": "Licenciatura", "maestria": "Maestría", "doctorado": "Doctorado",
           "especialidad": "Especialidad", "diplomado": "Diplomado"}
TIPOS = {"obligatoria": "Obligatoria", "trabajo_final": "Trabajo final", "electiva": "Electiva",
         "electiva_a": "Electiva A", "electiva_b": "Electiva B", "casilla_electiva": "Electiva",
         "casilla_electiva_a": "Electiva A", "casilla_electiva_b": "Electiva B"}
GRUPOS_ELECTIVAS = {"electiva_a": "Electivas A", "electiva_b": "Electivas B", "electiva": "Electivas"}
ORDINALES = ["", "Primer", "Segundo", "Tercer", "Cuarto", "Quinto", "Sexto", "Séptimo", "Octavo", "Noveno",
             "Décimo"]


def listar() -> list[dict]:
    return get_db().q(
        """SELECT p.*, pr.nombre AS programa, pr.nivel,
                  (SELECT COUNT(*) FROM plan_asignatura WHERE plan_id = p.id AND asignatura_id IS NOT NULL) AS n_asignaturas,
                  (SELECT COUNT(*) FROM observacion_plan WHERE plan_id = p.id AND estado = 'pendiente') AS n_pendientes
           FROM plan_estudios p JOIN programa pr ON pr.id = p.programa_id
           ORDER BY CASE pr.nivel WHEN 'licenciatura' THEN 1 WHEN 'maestria' THEN 2 ELSE 3 END, pr.nombre,
                    p.vigente_desde DESC""")


def obtener(pid: int) -> dict | None:
    filas = get_db().q("""SELECT p.*, pr.nombre AS programa, pr.nivel FROM plan_estudios p
                          JOIN programa pr ON pr.id = p.programa_id WHERE p.id = ?""", [pid])
    return filas[0] if filas else None


def asignaturas(pid: int) -> list[dict]:
    """Asignaturas y casillas del plan, en el orden del documento, con sus requisitos."""
    filas = get_db().q(
        """SELECT pa.*, a.sigla, a.nombre, a.de_la_carrera FROM plan_asignatura pa
           LEFT JOIN asignatura a ON a.id = pa.asignatura_id WHERE pa.plan_id = ? ORDER BY pa.orden""", [pid])
    requisitos = {}
    for r in get_db().q("""SELECT r.* FROM requisito r JOIN plan_asignatura pa ON pa.id = r.plan_asignatura_id
                           WHERE pa.plan_id = ? ORDER BY r.id""", [pid]):
        requisitos.setdefault(r["plan_asignatura_id"], []).append("Egresado" if r["condicion"] else r["sigla"])
    for f in filas:
        f["requisitos"] = requisitos.get(f["id"], [])
    return filas


def por_semestre(pid: int) -> list[tuple[int, str | None, list[dict]]]:
    """[(semestre, ciclo, filas)] de las asignaturas y casillas ubicadas en un semestre."""
    res = []
    for f in asignaturas(pid):
        if f["semestre"] is None:
            continue
        if not res or res[-1][0] != f["semestre"]:
            res.append((f["semestre"], f["ciclo"], []))
        res[-1][2].append(f)
    return res


def electivas(pid: int) -> dict[str, list[dict]]:
    """{'electiva_a': [...], ...}: las listas de asignaturas electivas del plan."""
    res = {}
    for f in asignaturas(pid):
        if f["semestre"] is None and f["tipo"] in GRUPOS_ELECTIVAS:
            res.setdefault(f["tipo"], []).append(f)
    return res


def totales(pid: int) -> dict:
    return importar_planes.totales(get_db().conn, pid)


def observaciones(pid: int) -> list[dict]:
    return get_db().q("""SELECT o.*, u.nombres || ' ' || u.apellidos AS resuelta_por_nombre FROM observacion_plan o
                         LEFT JOIN usuario u ON u.id = o.resuelta_por WHERE o.plan_id = ?
                         ORDER BY o.estado = 'resuelta', o.id""", [pid])


def resolver(oid: int, resolucion: str, uid: int) -> str | None:
    resolucion = (resolucion or "").strip()
    if not resolucion:
        return "Indique cómo se resolvió (p. ej., «Confirmado con la Dirección Académica: …»)."
    if len(resolucion) > 1000:
        return "La resolución admite hasta 1.000 caracteres."
    get_db().execute(f"""UPDATE observacion_plan SET estado = 'resuelta', resolucion = ?, resuelta_por = ?,
                         resuelta_en = {AHORA} WHERE id = ?""", [resolucion, uid, oid])
    return None


def observacion(oid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM observacion_plan WHERE id = ?", [oid])
    return filas[0] if filas else None
