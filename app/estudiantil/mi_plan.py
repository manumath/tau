"""«Mi plan de estudios» (PLAN §67, etapa 1): el estudiante ve la malla de su plan y marca lo que aprobó, solo como ayuda
personal. TAU no tiene sus notas: las marcas son suyas, privadas, y no van a informes ni a la Dirección; si decide
compartirlas, su tutor las ve en las reuniones.
"""
from app.academico import planes
from app.comun.db import get_db
from app.estudiantil import tutoria

OBLIGATORIAS = ("obligatoria", "trabajo_final")


def plan_de(externo_id: int) -> dict | None:
    """El plan de su licenciatura (el del periodo más reciente con plan), si está registrado y no es un borrador."""
    f = get_db().q("""SELECT plan_id FROM estudiante WHERE externo_id = ? AND plan_id IS NOT NULL
                      ORDER BY desde DESC, id DESC LIMIT 1""", [externo_id])
    p = planes.obtener(f[0]["plan_id"]) if f else None
    return p if p and p["estado"] != "elaboracion" else None


def aprobadas(externo_id: int) -> set[int]:
    return {f["asignatura_id"] for f in get_db().q("SELECT asignatura_id FROM estudiante_aprobada WHERE externo_id = ?",
                                                    [externo_id])}


def comparte(externo_id: int) -> bool:
    f = get_db().q("SELECT comparte_plan_tutor FROM cuenta_estudiante WHERE externo_id = ?", [externo_id])
    return bool(f and f[0]["comparte_plan_tutor"])


def fijar_comparte(externo_id: int, valor: bool):
    get_db().execute("UPDATE cuenta_estudiante SET comparte_plan_tutor = ? WHERE externo_id = ?", [int(valor), externo_id])


def marcar(externo_id: int, asignatura_id: int, plan_id: int) -> bool | None:
    """Alterna la marca de una asignatura del plan. → el nuevo estado (True: aprobada), o None si no es del plan."""
    if not get_db().q("SELECT 1 FROM plan_asignatura WHERE plan_id = ? AND asignatura_id = ?", [plan_id, asignatura_id]):
        return None
    if asignatura_id in aprobadas(externo_id):
        get_db().execute("DELETE FROM estudiante_aprobada WHERE externo_id = ? AND asignatura_id = ?",
                         [externo_id, asignatura_id])
        return False
    get_db().t.estudiante_aprobada.insert(externo_id=externo_id, asignatura_id=asignatura_id)
    return True


def avance(externo_id: int, plan: dict) -> dict:
    """Avance del estudiante en el plan: por semestre, cada asignatura con su estado (aprobada, disponible para cursar o
    bloqueada por un requisito), el avance en las obligatorias y las electivas aprobadas."""
    aprob = aprobadas(externo_id)
    filas = planes.asignaturas(plan["id"])
    siglas_aprobadas = {f["sigla"] for f in filas if f["asignatura_id"] in aprob}
    oblig = [f for f in filas if f["tipo"] in OBLIGATORIAS and f["asignatura_id"]]
    pendientes_oblig = [f for f in oblig if f["asignatura_id"] not in aprob]

    def estado(f):
        if f["asignatura_id"] in aprob:
            return "aprobada"
        faltan = [r for r in f["requisitos"] if r != "Egresado" and r not in siglas_aprobadas]
        if "Egresado" in f["requisitos"] and len([x for x in pendientes_oblig if x["id"] != f["id"]]) > 0:
            faltan.append("Egresado")
        return "disponible" if not faltan else "bloqueada"
    semestres = []
    for s, ciclo, fs in planes.por_semestre(plan["id"]):
        semestres.append({"semestre": s, "ciclo": ciclo, "filas": [
            {**f, "estado": estado(f) if f["asignatura_id"] else None} for f in fs]})
    electivas = [{**f, "estado": estado(f)} for f in filas if f["semestre"] is None and f["asignatura_id"]
                 and f["tipo"] in planes.GRUPOS_ELECTIVAS]
    hechas = sum(f["asignatura_id"] in aprob for f in oblig)
    return {"plan": plan, "semestres": semestres, "electivas": electivas, "obligatorias": len(oblig), "hechas": hechas,
            "pct": round(100 * hechas / len(oblig)) if oblig else 0,
            "electivas_aprobadas": sum(e["estado"] == "aprobada" for e in electivas),
            "disponibles": [f for s in semestres for f in s["filas"] if f["estado"] == "disponible"
                            and f["tipo"] in OBLIGATORIAS]}


def para_tutor(tutor_id: int, externo_id: int) -> dict | None:
    """El avance de un tutorado, solo si es su tutor(a) y el estudiante decidió compartirlo."""
    if not tutoria.es_tutor_de(tutor_id, externo_id) or not comparte(externo_id):
        return None
    plan = plan_de(externo_id)
    return avance(externo_id, plan) if plan else None
