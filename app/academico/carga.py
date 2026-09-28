"""Carga horaria por semestre (PLAN.md, sección 24, paso 3.4).

- La carga contratada y su distribución por actividad se registran en el **vínculo con la Carrera**
  (Usuarios → Vínculo; app.comun.vinculos): 32, 64, 96, 128 o 160 h/mes, en unidades de 32 h/mes,
  con la docencia, investigación, extensión, gestión y otras que la componen.
- En cada semestre (I o II) rige el periodo de vínculo vigente al inicio del semestre. La docencia
  prevista se compara con la asignada en la oferta: 32 h/mes por materia como titular (grado o
  maestría). No suman los auxiliares ni los cursos de verano e invierno.
- Jornada completa equivalente (anexo de acreditación) = carga contratada / 160.
"""
from app.academico import oferta
from app.comun import vinculos
from app.comun.db import get_db

UNIDAD = vinculos.UNIDAD_CARGA
CARGAS = vinculos.CARGAS
TIEMPO_COMPLETO = CARGAS[-1]
ACTIVIDADES = vinculos.ACTIVIDADES
SEMESTRES = ("I", "II")


def vinculo_en(usuario_id: int, fecha: str) -> dict | None:
    """El periodo de vínculo que cubre la fecha."""
    return vinculos.vigente(usuario_id, fecha)


def resumen(usuario_id: int, gestion: dict) -> dict:
    """Vínculo, carga contratada, distribución prevista, docencia asignada y avisos del semestre."""
    v = vinculo_en(usuario_id, gestion["fecha_inicio"])
    c = vinculos.carga_de(v)
    materias = oferta.materias_de(usuario_id, gestion["id"])
    asignada = oferta.horas_de_docencia(usuario_id, gestion["id"])
    prevista = c["actividades"]["docencia"] if c else None
    avisos = []
    if not v:
        avisos.append("Sin vínculo con la Carrera al inicio del semestre.")
    elif not c:
        avisos.append("Falta registrar la carga contratada en su vínculo con la Carrera.")
    elif asignada != prevista:
        n = abs(prevista - asignada) // oferta.HORAS_POR_MATERIA
        materias_txt = "1 materia" if n == 1 else f"{n} materias"
        avisos.append((f"Falta asignar {materias_txt}" if asignada < prevista else f"Tiene {materias_txt} más de lo previsto")
                      + f" (docencia prevista: {prevista} h/mes; asignada: {asignada} h/mes).")
    return {"vinculo": v, "carga": c, "contratada": c["horas"] if c else None, "materias": materias,
            "prevista": prevista, "asignada": asignada, "avisos": avisos}


def en_proyectos(vid: int) -> list[dict]:
    """Carga de un periodo de vínculo asignada por los responsables en proyectos institucionales
    (sale de la investigación o la extensión; ver app.investigacion.carga_proyectos)."""
    return get_db().q(
        """SELECT p.id, p.nombre, p.clase, pc.horas FROM participante_carga pc
           JOIN proyecto_participante pp ON pp.id = pc.participante_id JOIN proyecto p ON p.id = pp.proyecto_id
           WHERE pc.vinculo_id = ? ORDER BY p.nombre""", [vid])


def personas(gestion: dict) -> list[dict]:
    """Quienes tienen vínculo con la Carrera al inicio del semestre o dictan como titulares en él."""
    ids = [f["usuario_id"] for f in get_db().q(
        """SELECT usuario_id FROM vinculo WHERE unidad_id = :u
                  AND COALESCE(fecha_inicio, '0000-01-01') <= :f AND COALESCE(fecha_fin, '9999-12-31') >= :f
           UNION SELECT d.usuario_id FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
                 WHERE o.gestion_id = :g AND d.rol = 'titular'""",
        {"u": vinculos.carrera(), "f": gestion["fecha_inicio"], "g": gestion["id"]})]
    res = []
    for p in get_db().q(f"""SELECT id, nombres, apellidos FROM usuario WHERE id IN ({",".join("?" * len(ids)) or "NULL"})
                            ORDER BY apellidos, nombres""", ids):
        res.append({**p, **resumen(p["id"], gestion)})
    return res


def contratada_en(usuario_id: int, fecha: str) -> int | None:
    """Carga contratada (h/mes) del vínculo con la Carrera que cubre la fecha."""
    c = vinculos.carga_de(vinculo_en(usuario_id, fecha))
    return c["horas"] if c else None
