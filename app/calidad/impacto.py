"""Impacto de los proyectos de interacción social (PLAN §57, etapa 8; Política de Calidad de la UMSA, objetivo 6): a
cuántos llegó cada proyecto, qué cambió y si el impacto está comprobado con una evidencia. El indicador «Proyectos con
impacto social comprobado» (`auto:impacto_interaccion_social`) divide entre los vigentes en el año."""
from app.comun.db import AHORA, get_db


def proyectos() -> list[dict]:
    """Proyectos institucionales de interacción social (no en formulación), con su impacto si se registró."""
    return get_db().q(
        """SELECT p.id, p.nombre, p.estado, p.fecha_inicio, p.fecha_fin, i.beneficiarios, i.descripcion AS impacto,
                  i.comprobado, i.evidencia_id, e.titulo AS evidencia_titulo, i.registrado_en
           FROM proyecto p LEFT JOIN impacto_proyecto i ON i.proyecto_id = p.id
           LEFT JOIN evidencia_calidad e ON e.id = i.evidencia_id
           WHERE p.tipo = 'institucional' AND p.clase = 'interaccion_social' AND p.estado != 'formulacion'
           ORDER BY p.estado = 'finalizado', COALESCE(p.fecha_inicio, '') DESC, p.nombre""")


def proyecto(pid: int) -> dict | None:
    return next((p for p in proyectos() if p["id"] == pid), None)


def es_responsable(uid: int, pid: int) -> bool:
    return bool(get_db().q("""SELECT 1 FROM proyecto_participante WHERE proyecto_id = ? AND investigador_id = ?
                                AND rol IN ('responsable', 'co_responsable')""", [pid, uid]))


def tiene_proyectos(uid: int) -> bool:
    """¿Es responsable de algún proyecto institucional de interacción social? (para el menú)."""
    return bool(get_db().q("""SELECT 1 FROM proyecto p JOIN proyecto_participante pp ON pp.proyecto_id = p.id
                              WHERE p.tipo = 'institucional' AND p.clase = 'interaccion_social' AND p.estado != 'formulacion'
                                AND pp.investigador_id = ? AND pp.rol IN ('responsable', 'co_responsable') LIMIT 1""",
                           [uid]))


def validar(d: dict, evidencias_validas: set[int]) -> tuple[dict, list[str]]:
    errores: list[str] = []
    b = str(d.get("beneficiarios") or "").strip()
    x = {"beneficiarios": int(b) if b.isdigit() else None,
         "descripcion": (d.get("descripcion") or "").strip()[:3000] or None,
         "comprobado": int(str(d.get("comprobado") or "") in ("1", "on", "true"))}
    if b and x["beneficiarios"] is None:
        errores.append("Los beneficiarios son un número entero.")
    e = str(d.get("evidencia_id") or "").strip()
    x["evidencia_id"] = int(e) if e.isdigit() and int(e) in evidencias_validas else None
    if e and x["evidencia_id"] is None:
        errores.append("Elija una evidencia del repositorio.")
    if x["comprobado"] and not x["evidencia_id"]:
        errores.append("Un impacto comprobado necesita su evidencia (informe de evaluación, testimonio, registro).")
    if x["comprobado"] and not x["descripcion"]:
        errores.append("Describa el impacto comprobado.")
    return x, errores


def guardar(pid: int, x: dict, uid: int):
    get_db().execute(
        f"""INSERT INTO impacto_proyecto (proyecto_id, beneficiarios, descripcion, comprobado, evidencia_id, registrado_por)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (proyecto_id) DO UPDATE SET beneficiarios = excluded.beneficiarios,
                descripcion = excluded.descripcion, comprobado = excluded.comprobado, evidencia_id = excluded.evidencia_id,
                registrado_por = excluded.registrado_por, registrado_en = {AHORA}""",
        [pid, x["beneficiarios"], x["descripcion"], x["comprobado"], x["evidencia_id"], uid])
