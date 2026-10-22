"""Tutoría y orientación (PLAN §49): cada estudiante que cursa tiene un tutor (docente con vínculo) y el tutor registra
sus reuniones y derivaciones.

Las reuniones son confidenciales: las ve su autor y la Dirección de Carrera (`ver_tutorias_detalle`, con registro en la
auditoría); el estudiante no las ve y los informes solo usan cifras agregadas. Un tutor nuevo no ve las reuniones del anterior.
"""
from datetime import date, timedelta

from app.comun import notificaciones, usuarios
from app.comun.db import auditar, get_db, transaccion
from app.estudiantil import cohortes

TEMAS = {"academico": "Académico", "economico": "Económico", "salud": "Salud", "vocacional": "Vocacional",
         "convivencia": "Convivencia", "otro": "Otro"}
DERIVACIONES = {"ninguna": "Sin derivación", "bienestar": "Bienestar universitario", "psicologia": "Apoyo psicológico",
                "academica": "Apoyo académico", "economica": "Ayuda económica", "salud": "Salud", "otra": "Otra"}
MODALIDADES = {"presencial": "Presencial", "virtual": "Virtual"}


def tutores_elegibles() -> list[dict]:
    """Cuentas activas con vínculo vigente con la Carrera."""
    return [u for u in usuarios.listar() if u["activo"] and u["categoria"]]


# --- Asignación ----------------------------------------------------------------------------------------------------

def cursando() -> list[dict]:
    """Estudiantes que cursan, con su tutor vigente, cuántas reuniones tienen y la última (para la Dirección)."""
    filas = get_db().q(
        """SELECT pe.id AS externo_id, pe.nombres, pe.apellidos, es.cohorte_anio, es.cohorte_ciclo, es.registro_universitario,
                  t.tutor_id, u.nombres AS tutor_nombres, u.apellidos AS tutor_apellidos,
                  (SELECT COUNT(*) FROM tutoria_reunion r WHERE r.externo_id = pe.id) AS reuniones,
                  (SELECT MAX(fecha) FROM tutoria_reunion r WHERE r.externo_id = pe.id) AS ultima
           FROM estudiante es JOIN persona_externa pe ON pe.id = es.externo_id
           LEFT JOIN tutoria_asignacion t ON t.externo_id = pe.id AND t.hasta IS NULL
           LEFT JOIN usuario u ON u.id = t.tutor_id
           WHERE es.nivel = 'licenciatura' AND es.del_programa = 1 AND es.cohorte_anio IS NOT NULL AND es.estado = 'cursando'
           ORDER BY es.cohorte_anio, es.cohorte_ciclo, pe.apellidos, pe.nombres""")
    return filas


def asignar(externo_id: int, tutor_id: int, uid: int | None) -> list[str]:
    """Asigna (o cambia) el tutor de un estudiante que cursa."""
    tutor = next((t for t in tutores_elegibles() if t["id"] == tutor_id), None)
    if not tutor:
        return ["Elija un docente con vínculo vigente."]
    est = get_db().q("""SELECT 1 FROM estudiante WHERE externo_id = ? AND nivel = 'licenciatura' AND del_programa = 1
                        AND estado = 'cursando'""", [externo_id])
    if not est:
        return ["Solo se asigna tutor a quien cursa la licenciatura."]
    vigente = get_db().q("SELECT * FROM tutoria_asignacion WHERE externo_id = ? AND hasta IS NULL", [externo_id])
    if vigente and vigente[0]["tutor_id"] == tutor_id:
        return []
    hoy = date.today().isoformat()
    with transaccion():
        if vigente:
            get_db().execute("UPDATE tutoria_asignacion SET hasta = ? WHERE id = ?", [max(hoy, vigente[0]["desde"]), vigente[0]["id"]])
        get_db().t.tutoria_asignacion.insert(externo_id=externo_id, tutor_id=tutor_id, desde=hoy, asignado_por=uid)
    auditar(uid, "asignar_tutor", "persona_externa", externo_id, f"tutor {tutor_id}")
    return []


def asignar_cohorte(anio: int, ciclo: str, tutor_id: int, uid: int | None) -> int:
    """Asigna el tutor a los estudiantes de la cohorte que cursan y aún no tienen. → cuántos."""
    n = 0
    for f in cursando():
        if f["cohorte_anio"] == anio and f["cohorte_ciclo"] == ciclo and f["tutor_id"] is None:
            if not asignar(f["externo_id"], tutor_id, uid):
                n += 1
    if n:
        t = usuarios.por_id(tutor_id)
        notificaciones.avisar(t, "Le asignaron estudiantes como tutor", f"Tiene {n} estudiante(s) nuevo(s) de la cohorte "
                              f"{cohortes.texto(anio, ciclo)}.", "/tutoria")
    return n


def terminar(externo_id: int, uid: int | None) -> bool:
    filas = get_db().q("SELECT * FROM tutoria_asignacion WHERE externo_id = ? AND hasta IS NULL", [externo_id])
    if not filas:
        return False
    get_db().execute("UPDATE tutoria_asignacion SET hasta = ? WHERE id = ?", [max(date.today().isoformat(), filas[0]["desde"]),
                                                                              filas[0]["id"]])
    auditar(uid, "terminar_tutoria", "persona_externa", externo_id)
    return True


def tutorados(tutor_id: int) -> list[dict]:
    """Estudiantes que tiene asignados el tutor, con cuántas reuniones suyas hay y la última."""
    return get_db().q(
        """SELECT pe.id AS externo_id, pe.nombres, pe.apellidos, es.cohorte_anio, es.cohorte_ciclo, es.registro_universitario,
                  es.estado,
                  (SELECT COUNT(*) FROM tutoria_reunion r WHERE r.externo_id = pe.id AND r.tutor_id = t.tutor_id) AS reuniones,
                  (SELECT MAX(fecha) FROM tutoria_reunion r WHERE r.externo_id = pe.id AND r.tutor_id = t.tutor_id) AS ultima
           FROM tutoria_asignacion t JOIN persona_externa pe ON pe.id = t.externo_id
           JOIN estudiante es ON es.externo_id = pe.id AND es.nivel = 'licenciatura' AND es.cohorte_anio IS NOT NULL
           WHERE t.tutor_id = ? AND t.hasta IS NULL ORDER BY es.cohorte_anio, pe.apellidos, pe.nombres""", [tutor_id])


def es_tutor_de(tutor_id: int, externo_id: int) -> bool:
    return bool(get_db().q("SELECT 1 FROM tutoria_asignacion WHERE tutor_id = ? AND externo_id = ? AND hasta IS NULL",
                           [tutor_id, externo_id]))


# --- Reuniones -----------------------------------------------------------------------------------------------------

def validar(d: dict) -> tuple[dict, list[str]]:
    errores = []
    fecha = (d.get("fecha") or "").strip()
    try:
        if date.fromisoformat(fecha) > date.today():
            errores.append("La fecha no puede ser futura.")
        elif date.fromisoformat(fecha).year < 2000:
            errores.append("La fecha no es válida.")
    except ValueError:
        errores.append("Indique la fecha de la reunión.")
    if d.get("tema") not in TEMAS:
        errores.append("Elija el tema.")
    if (d.get("modalidad") or "presencial") not in MODALIDADES:
        errores.append("Elija la modalidad.")
    derivacion = d.get("derivacion") or "ninguna"
    if derivacion not in DERIVACIONES:
        errores.append("La derivación no es válida.")
    resumen, acuerdos = (d.get("resumen") or "").strip(), (d.get("acuerdos") or "").strip()
    if len(resumen) > 3000 or len(acuerdos) > 2000:
        errores.append("El texto es demasiado largo.")
    return {"fecha": fecha, "modalidad": d.get("modalidad") or "presencial", "tema": d.get("tema"), "resumen": resumen or None,
            "derivacion": derivacion, "acuerdos": acuerdos or None}, errores


def registrar(externo_id: int, tutor_id: int, d: dict) -> list[str]:
    if not es_tutor_de(tutor_id, externo_id):
        return ["Ese estudiante no está entre sus tutorados."]
    datos, errores = validar(d)
    if not errores:
        get_db().t.tutoria_reunion.insert(externo_id=externo_id, tutor_id=tutor_id, **datos)
        auditar(tutor_id, "registrar_tutoria", "persona_externa", externo_id, datos["fecha"])
    return errores


def obtener(rid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM tutoria_reunion WHERE id = ?", [rid])
    return filas[0] if filas else None


def editar(rid: int, tutor_id: int, d: dict) -> list[str]:
    r = obtener(rid)
    if not r or r["tutor_id"] != tutor_id:
        return ["Reunión no encontrada."]
    datos, errores = validar(d)
    if not errores:
        get_db().t.tutoria_reunion.update(id=rid, **datos)
        get_db().execute("UPDATE tutoria_reunion SET actualizado_en = datetime('now') WHERE id = ?", [rid])
    return errores


def eliminar(rid: int, tutor_id: int) -> bool:
    r = obtener(rid)
    if not r or r["tutor_id"] != tutor_id:
        return False
    get_db().execute("DELETE FROM tutoria_reunion WHERE id = ?", [rid])
    auditar(tutor_id, "eliminar_tutoria", "persona_externa", r["externo_id"], r["fecha"])
    return True


def reuniones(externo_id: int, tutor_id: int | None = None) -> list[dict]:
    """Reuniones del estudiante: las de un tutor, o (sin `tutor_id`) todas, solo para la Dirección."""
    filas = get_db().q(
        """SELECT r.*, u.nombres AS tutor_nombres, u.apellidos AS tutor_apellidos FROM tutoria_reunion r
           JOIN usuario u ON u.id = r.tutor_id WHERE r.externo_id = ? AND (? IS NULL OR r.tutor_id = ?)
           ORDER BY r.fecha DESC, r.id DESC""", [externo_id, tutor_id, tutor_id])
    return filas


# --- Cifras agregadas -----------------------------------------------------------------------------------------------

def indicadores(hoy: date | None = None) -> dict:
    """Cobertura y actividad de la tutoría, sin datos personales."""
    hoy = hoy or date.today()
    est = cursando()
    desde = (hoy - timedelta(days=365)).isoformat()
    con_tutor = sum(e["tutor_id"] is not None for e in est)
    sin_reunion = sum(1 for e in est if e["tutor_id"] is not None and (not e["ultima"] or e["ultima"] < desde))
    db = get_db()
    por_anio = {f["anio"]: f["n"] for f in db.q("""SELECT substr(fecha, 1, 4) AS anio, COUNT(*) n FROM tutoria_reunion
                                                   GROUP BY anio ORDER BY anio DESC LIMIT 5""")}
    return {"cursando": len(est), "con_tutor": con_tutor, "cobertura": con_tutor / len(est) if est else None,
            "sin_reunion_12m": sin_reunion,
            "tutores": db.q("SELECT COUNT(DISTINCT tutor_id) n FROM tutoria_asignacion WHERE hasta IS NULL")[0]["n"],
            "reuniones": db.q("SELECT COUNT(*) n FROM tutoria_reunion")[0]["n"], "por_anio": por_anio,
            "temas": {t: db.q("SELECT COUNT(*) n FROM tutoria_reunion WHERE tema = ?", [k])[0]["n"] for k, t in TEMAS.items()},
            "derivaciones": {t: db.q("SELECT COUNT(*) n FROM tutoria_reunion WHERE derivacion = ?", [k])[0]["n"]
                             for k, t in DERIVACIONES.items() if k != "ninguna"}}
