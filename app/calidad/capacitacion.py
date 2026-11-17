"""Capacitación del personal de la Carrera (PLAN §57, etapa 8; Política de Calidad de la UMSA, objetivo 4): cursos,
talleres, diplomados y pasantías de formación que concluyó cada académico. Una capacitación cuenta en el año en que
concluyó; el indicador «Personal capacitado» (`auto:personal_capacitado`) divide entre los académicos vinculados."""
from datetime import date

from app.informes import anexo
from app.comun import vinculos
from app.comun.db import get_db

AREAS = {"disciplinar": "Disciplinar (matemática)", "pedagogica": "Pedagógica o didáctica", "investigacion": "Investigación",
         "gestion": "Gestión", "ia_digital": "IA y competencias digitales", "otra": "Otra"}   # ia_digital: PLAN §59


def _texto(v, largo=300):
    return (v or "").strip()[:largo] or None


def personas() -> list[dict]:
    """Quienes tuvieron vínculo con la Carrera alguna vez (pueden tener capacitaciones de años anteriores)."""
    return vinculos.personas_en_rango("0000-01-01", date.today().isoformat())


def listar(anio: int | None = None, usuario: int | None = None) -> list[dict]:
    return get_db().q(
        """SELECT c.*, u.nombres, u.apellidos, e.titulo AS evidencia_titulo FROM capacitacion c
           JOIN usuario u ON u.id = c.usuario_id LEFT JOIN evidencia_calidad e ON e.id = c.evidencia_id
           WHERE (:a IS NULL OR substr(c.fecha_fin, 1, 4) = :a) AND (:u IS NULL OR c.usuario_id = :u)
           ORDER BY c.fecha_fin DESC, u.apellidos""", {"a": str(anio) if anio else None, "u": usuario})


def obtener(cid: int) -> dict | None:
    f = get_db().q("SELECT * FROM capacitacion WHERE id = ?", [cid])
    return f[0] if f else None


def resumen(anio: int) -> dict:
    """Académicos vinculados en el año, cuántos concluyeron alguna capacitación y las horas en total."""
    gente = anexo.cuerpo_academico(anio, date.today().isoformat())["personas"]
    del_anio = listar(anio)
    con = {c["usuario_id"] for c in del_anio}
    return {"vinculados": len(gente), "capacitados": sum(p["id"] in con for p in gente), "cursos": len(del_anio),
            "horas": sum(c["horas"] or 0 for c in del_anio)}


def validar(d: dict, evidencias_validas: set[int]) -> tuple[dict, list[str]]:
    errores: list[str] = []
    x = {"titulo": _texto(d.get("titulo")), "institucion": _texto(d.get("institucion")), "area": d.get("area") or ""}
    if not x["titulo"]:
        errores.append("Indique el nombre de la capacitación.")
    if x["area"] not in AREAS:
        errores.append("Elija el área.")
    u = str(d.get("usuario_id") or "")
    x["usuario_id"] = int(u) if u.isdigit() and int(u) in {p["id"] for p in personas()} else None
    if x["usuario_id"] is None:
        errores.append("Elija a la persona.")
    for k, campo in (("fecha_inicio", "la fecha de inicio"), ("fecha_fin", "la fecha en que concluyó")):
        v = (d.get(k) or "").strip()
        try:
            x[k] = date.fromisoformat(v).isoformat()
        except ValueError:
            x[k] = v or None
            errores.append(f"Indique {campo}.")
    if x.get("fecha_inicio") and x.get("fecha_fin") and x["fecha_fin"] < x["fecha_inicio"] and not errores:
        errores.append("La fecha en que concluyó no puede ser anterior a la de inicio.")
    if x.get("fecha_fin") and x["fecha_fin"] > date.today().isoformat() and not errores:
        errores.append("Registre la capacitación cuando haya concluido.")
    h = str(d.get("horas") or "").strip()
    x["horas"] = int(h) if h.isdigit() and 1 <= int(h) <= 2000 else None
    if h and x["horas"] is None:
        errores.append("Las horas van de 1 a 2000.")
    e = str(d.get("evidencia_id") or "").strip()
    x["evidencia_id"] = int(e) if e.isdigit() and int(e) in evidencias_validas else None
    if e and x["evidencia_id"] is None:
        errores.append("Elija una evidencia del repositorio.")
    return x, errores


CAMPOS = ("usuario_id", "titulo", "institucion", "area", "horas", "fecha_inicio", "fecha_fin", "evidencia_id")


def crear(x: dict, uid: int) -> int:
    return get_db().t.capacitacion.insert(registrado_por=uid, **{k: x[k] for k in CAMPOS})["id"]


def actualizar(cid: int, x: dict):
    get_db().t.capacitacion.update({k: x[k] for k in CAMPOS}, cid)


def eliminar(cid: int):
    get_db().execute("DELETE FROM capacitacion WHERE id = ?", [cid])
