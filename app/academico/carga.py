"""Carga horaria por semestre (PLAN.md, sección 24, paso 3.4).

- La carga contratada y su distribución por actividad se registran en el **vínculo con la Carrera**
  (Usuarios → Vínculo; app.comun.vinculos): 32, 64, 96, 128 o 160 h/mes, en unidades de 32 h/mes,
  con la docencia, investigación, extensión, gestión y otras que la componen.
- En cada semestre (I o II) rige el periodo de vínculo vigente al inicio del semestre. La docencia
  prevista se compara con la asignada en la oferta: 32 h/mes por materia como titular (grado o
  maestría). No suman los auxiliares ni los cursos de verano e invierno.
- Jornada completa equivalente (anexo de acreditación) = carga contratada / 160.
"""
from datetime import date, timedelta

from app.academico import gestiones, oferta
from app.comun import vinculos
from app.comun.db import get_db

UNIDAD = vinculos.UNIDAD_CARGA
CARGAS = vinculos.CARGAS
TIEMPO_COMPLETO = CARGAS[-1]
ACTIVIDADES = vinculos.ACTIVIDADES
SEMESTRES = ("I", "II")
# Categorías que no necesariamente tienen carga contratada (p. ej., un invitado que solo investiga).
SIN_CARGA_OBLIGATORIA = ("invitado", "externo")


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
        if v["categoria"] not in SIN_CARGA_OBLIGATORIA or materias:
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


# --- Tableros -------------------------------------------------------------------------------------

def semestre_de_referencia(hoy: str | None = None) -> dict | None:
    """El semestre en curso o, si hoy es temporada (invierno, verano) o receso, el próximo; si no
    hay próximo, el último."""
    h = hoy or date.today().isoformat()
    filas = get_db().q(
        """SELECT * FROM gestion_academica WHERE tipo IN ('I', 'II') AND fecha_fin >= ?
           ORDER BY fecha_inicio LIMIT 1""", [h]) or get_db().q(
        "SELECT * FROM gestion_academica WHERE tipo IN ('I', 'II') ORDER BY fecha_inicio DESC LIMIT 1")
    return filas[0] if filas else None


def contratos_por_vencer(dias: int = 30) -> list[dict]:
    """Periodos de vínculo vigentes que terminan en los próximos `dias` días."""
    hoy = vinculos.hoy()
    return get_db().q(
        """SELECT v.id, v.usuario_id, v.categoria, v.fecha_fin, u.nombres, u.apellidos FROM vinculo v
           JOIN usuario u ON u.id = v.usuario_id
           WHERE v.fecha_fin BETWEEN ? AND ? AND COALESCE(v.fecha_inicio, '0000-01-01') <= ?
             AND NOT EXISTS (SELECT 1 FROM vinculo n WHERE n.usuario_id = v.usuario_id AND n.fecha_inicio > v.fecha_fin)
           ORDER BY v.fecha_fin, u.apellidos""",
        [hoy.isoformat(), (hoy + timedelta(days=dias)).isoformat(), hoy.isoformat()])


def vigentes_sin_carga() -> list[dict]:
    """Docentes (titulares, contratados, interinos) con vínculo vigente sin carga contratada."""
    h = vinculos.hoy().isoformat()
    return get_db().q(
        f"""SELECT v.usuario_id, u.nombres, u.apellidos, v.categoria FROM vinculo v JOIN usuario u ON u.id = v.usuario_id
            WHERE v.horas_contratadas IS NULL AND v.categoria NOT IN ({",".join("?" * len(SIN_CARGA_OBLIGATORIA))})
              AND COALESCE(v.fecha_inicio, '0000-01-01') <= ? AND COALESCE(v.fecha_fin, '9999-12-31') >= ?
            ORDER BY u.apellidos""", [*SIN_CARGA_OBLIGATORIA, h, h])


# --- Mi docencia ----------------------------------------------------------------------------------

def gestiones_de(usuario_id: int) -> list[dict]:
    """Gestiones en que dictó (con cualquier rol), más el semestre de referencia; recientes primero."""
    ids = {f["gestion_id"] for f in get_db().q(
        """SELECT DISTINCT o.gestion_id FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
           WHERE d.usuario_id = ?""", [usuario_id])}
    ref = semestre_de_referencia()
    if ref:
        ids.add(ref["id"])
    return [g for g in gestiones.listar() if g["id"] in ids]


def materias_con_detalle(usuario_id: int, gestion_id: int) -> list[dict]:
    """Paralelos que dicta en la gestión (titular o auxiliar), con inscritos."""
    return get_db().q(
        """SELECT a.sigla, a.nombre, o.paralelo, o.inscritos, d.rol FROM oferta_docente d
           JOIN oferta o ON o.id = d.oferta_id JOIN asignatura a ON a.id = o.asignatura_id
           WHERE d.usuario_id = ? AND o.gestion_id = ? ORDER BY d.rol = 'auxiliar', a.sigla, o.paralelo""",
        [usuario_id, gestion_id])


def proyectos_con_carga(usuario_id: int) -> list[dict]:
    """Su carga en proyectos en el periodo de vínculo vigente (la asignan los responsables)."""
    v = vinculos.vigente(usuario_id)
    return en_proyectos(v["id"]) if v else []
