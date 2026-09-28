"""Carga horaria de los participantes en proyectos institucionales (PLAN.md, sección 26).

- El responsable asigna a cada participante del instituto una carga en el proyecto (múltiplos de
  32 h/mes, o ninguna). Sale de la carga de **investigación** (proyectos de investigación) o de
  **extensión** (interacción social) que la Dirección de Carrera registró en su periodo de vínculo
  vigente; la suma en todos sus proyectos de esa clase no puede superarla.
- La asignación queda ligada a ese periodo de vínculo (`participante_carga.vinculo_id`) y rige solo
  mientras está vigente. Si el vínculo termina, la persona puede seguir como participante, pero
  figura sin carga. En un nuevo periodo de vínculo la carga no se reasigna sola: la define el
  responsable.
- Avisos a los responsables (en la pestaña «Pendientes» y por correo, una vez):
  - `desvinculado`: un participante con carga quedó sin vínculo (aunque siga en el proyecto);
  - `nuevo_vinculo`: un participante que tuvo carga en el proyecto volvió a vincularse y tiene
    carga libre de esa actividad. Si otro proyecto ya se la asignó toda, el aviso no aparece (y
    desaparece si ya estaba).
- Los avisos se revisan cuando cambia un vínculo (`vinculos.OYENTES`), al asignar carga y en el
  mantenimiento horario (los términos llegan con la fecha, sin que nadie edite nada).
"""
from app.comun import vinculos
from app.comun.db import AHORA, get_db
from app.investigacion import avisos, proyectos

UNIDAD = vinculos.UNIDAD_CARGA
TIPOS_AVISO = {"desvinculado": "Quedó sin vínculo", "nuevo_vinculo": "Nuevo periodo de vínculo"}


def _hoy() -> str:
    return vinculos.hoy().isoformat()


def admite(p: dict) -> bool:
    """Solo los proyectos institucionales (con clase) asignan carga."""
    return p["tipo"] == "institucional" and p.get("clase") in vinculos.ACTIVIDAD_DE_CLASE


def actividad(p: dict) -> str:
    return vinculos.ACTIVIDAD_DE_CLASE[p["clase"]]


def _asignadas(vid: int, clase: str, excluir_participante: int | None = None) -> int:
    """Horas de un periodo de vínculo asignadas hoy en proyectos de una clase."""
    return get_db().q(
        """SELECT COALESCE(SUM(pc.horas), 0) AS h FROM participante_carga pc
           JOIN proyecto_participante pp ON pp.id = pc.participante_id JOIN proyecto p ON p.id = pp.proyecto_id
           WHERE pc.vinculo_id = ? AND p.clase = ? AND pc.participante_id IS NOT ?
             AND (pp.fecha_hasta IS NULL OR pp.fecha_hasta > ?) AND p.estado != 'finalizado'""",
        [vid, clase, excluir_participante, _hoy()])[0]["h"]


def disponible(uid: int, p: dict, excluir_participante: int | None = None) -> dict:
    """Vínculo vigente hoy y horas de la actividad del proyecto: contratadas, asignadas en otros
    proyectos de la misma clase y libres."""
    v = vinculos.vigente(uid)
    c = vinculos.carga_de(v)
    contratadas = c["actividades"][actividad(p)] if c else 0
    asignadas = _asignadas(v["id"], p["clase"], excluir_participante) if v else 0
    return {"vinculo": v, "actividad": actividad(p), "contratadas": contratadas, "asignadas": asignadas,
            "libres": max(0, contratadas - asignadas)}


def actual(participante_id: int) -> dict | None:
    """La asignación que rige hoy (la del periodo de vínculo vigente), o None."""
    filas = get_db().q(
        """SELECT pc.* FROM participante_carga pc JOIN vinculo v ON v.id = pc.vinculo_id
           WHERE pc.participante_id = ? AND COALESCE(v.fecha_inicio, '0000-01-01') <= ?
             AND COALESCE(v.fecha_fin, '9999-12-31') >= ?""", [participante_id, _hoy(), _hoy()])
    return filas[0] if filas else None


def historial(participante_id: int) -> list[dict]:
    """Periodos con carga en el proyecto: horas, desde y hasta (el término del vínculo o la baja)."""
    filas = get_db().q(
        """SELECT pc.horas, pc.desde, v.fecha_fin, pp.fecha_hasta, v.categoria FROM participante_carga pc
           JOIN vinculo v ON v.id = pc.vinculo_id JOIN proyecto_participante pp ON pp.id = pc.participante_id
           WHERE pc.participante_id = ? ORDER BY pc.desde""", [participante_id])
    res = []
    for f in filas:
        fines = [x for x in (f["fecha_fin"], f["fecha_hasta"]) if x]
        res.append({"horas": f["horas"], "desde": f["desde"], "hasta": min(fines) if fines else None})
    return res


def opciones(uid: int, p: dict, participante_id: int | None = None) -> list[int]:
    """Horas que se pueden asignar: 0 y los múltiplos de 32 hasta lo libre (más lo ya asignado aquí)."""
    d = disponible(uid, p, excluir_participante=participante_id)
    return [0] + list(range(UNIDAD, d["libres"] + 1, UNIDAD))


def validar(uid: int, p: dict, horas, participante_id: int | None = None) -> tuple[int | None, str | None]:
    """→ (horas, error)."""
    h = int(horas) if str(horas or "0").isdigit() else None
    if h is None or h % UNIDAD:
        return None, "La carga en el proyecto es de 0, 32, 64… h/mes."
    if not h:
        return 0, None
    if not admite(p):
        return None, "Solo los proyectos institucionales asignan carga horaria."
    d = disponible(uid, p, excluir_participante=participante_id)
    act = vinculos.ACTIVIDADES[d["actividad"]].lower()
    if not d["vinculo"]:
        return None, "No tiene un vínculo vigente: puede participar, pero sin carga horaria."
    if not d["contratadas"]:
        return None, f"Su vínculo no tiene carga de {act}: puede participar, pero sin carga horaria."
    if h > d["libres"]:
        return None, (f"Tiene {d['libres']} h/mes de {act} libres en su vínculo (contratadas: {d['contratadas']}; "
                      f"asignadas en otros proyectos: {d['asignadas']}).")
    return h, None


def asignar(pid: int, participante_id: int, horas, por: int) -> str | None:
    """Fija la carga del participante en el proyecto para su periodo de vínculo vigente (0 la quita)."""
    p = proyectos.obtener(pid)
    part = proyectos.participante(pid, participante_id)
    if not p or not part:
        return "Participante no válido."
    if not part["investigador_id"]:
        return "Las personas externas no tienen carga horaria en el instituto."
    if part["fecha_hasta"] and part["fecha_hasta"] < _hoy():
        return "Ya no participa en el proyecto."
    if p["estado"] == "finalizado":
        return "El proyecto terminó."
    h, error = validar(part["investigador_id"], p, horas, participante_id)
    if error:
        return error
    v = vinculos.vigente(part["investigador_id"])
    if not v:
        return None  # sin vínculo y 0 horas: nada que hacer
    db = get_db()
    if h:
        db.execute(f"""INSERT INTO participante_carga (participante_id, vinculo_id, horas, desde, asignada_por)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT (participante_id, vinculo_id) DO UPDATE SET horas = excluded.horas,
                       asignada_por = excluded.asignada_por, asignada_en = {AHORA}""",
                   [participante_id, v["id"], h, max(_hoy(), v["fecha_inicio"] or _hoy()), por])
    else:
        db.execute("DELETE FROM participante_carga WHERE participante_id = ? AND vinculo_id = ?",
                   [participante_id, v["id"]])
    # El responsable ya decidió sobre este periodo de vínculo.
    db.execute(f"""UPDATE aviso_carga SET atendido_en = {AHORA}, atendido_por = ?
                   WHERE participante_id = ? AND vinculo_id = ? AND atendido_en IS NULL""",
               [por, participante_id, v["id"]])
    revisar(part["investigador_id"])
    return None


# --- Avisos ---------------------------------------------------------------------------------------------------

def _crear_aviso(pid: int, participante_id: int, vid: int, tipo: str) -> bool:
    """True si el aviso es nuevo (y hay que mandar el correo). Cada aviso se crea una sola vez."""
    if get_db().q("SELECT 1 FROM aviso_carga WHERE participante_id = ? AND vinculo_id = ? AND tipo = ?",
                  [participante_id, vid, tipo]):
        return False
    get_db().t.aviso_carga.insert(proyecto_id=pid, participante_id=participante_id, vinculo_id=vid, tipo=tipo)
    return True


def revisar(uid: int | None = None):
    """Crea los avisos que correspondan (para una persona o para todas) y da por atendidos los de
    «nuevo vínculo» que ya no aplican."""
    hoy = _hoy()
    filtro = "AND pp.investigador_id = ?" if uid else ""
    participaciones = get_db().q(
        f"""SELECT pp.id AS participante_id, pp.investigador_id AS uid, p.id AS pid, p.nombre, p.clase
            FROM proyecto_participante pp JOIN proyecto p ON p.id = pp.proyecto_id
            WHERE p.tipo = 'institucional' AND p.clase IS NOT NULL AND p.estado != 'finalizado'
              AND pp.investigador_id IS NOT NULL AND (pp.fecha_hasta IS NULL OR pp.fecha_hasta >= ?) {filtro}""",
        [hoy, uid] if uid else [hoy])
    for x in participaciones:
        previas = get_db().q(
            """SELECT pc.vinculo_id, pc.horas, v.fecha_inicio, v.fecha_fin FROM participante_carga pc
               JOIN vinculo v ON v.id = pc.vinculo_id WHERE pc.participante_id = ?
               ORDER BY COALESCE(v.fecha_inicio, '0000-01-01') DESC""", [x["participante_id"]])
        if not previas:
            continue  # nunca tuvo carga en este proyecto: no hay nada que avisar
        vig = vinculos.vigente(x["uid"])
        ultima = previas[0]
        if not vig:
            # Quedó sin vínculo con carga en el proyecto (aunque siga como participante).
            if ultima["fecha_fin"] and ultima["fecha_fin"] < hoy and _crear_aviso(
                    x["pid"], x["participante_id"], ultima["vinculo_id"], "desvinculado"):
                avisos.carga_desvinculado(x["pid"], x["uid"], ultima["horas"], ultima["fecha_fin"])
            continue
        if any(pc["vinculo_id"] == vig["id"] for pc in previas):
            continue  # ya tiene carga en el periodo vigente
        libres = disponible(x["uid"], {"tipo": "institucional", "clase": x["clase"]})["libres"]
        if libres and _crear_aviso(x["pid"], x["participante_id"], vig["id"], "nuevo_vinculo"):
            avisos.carga_nuevo_vinculo(x["pid"], x["uid"], libres, vinculos.ACTIVIDAD_DE_CLASE[x["clase"]])
        elif not libres:
            # Otro proyecto ya le asignó toda su carga: el aviso deja de aplicar.
            get_db().execute(f"""UPDATE aviso_carga SET atendido_en = {AHORA} WHERE participante_id = ?
                                 AND vinculo_id = ? AND tipo = 'nuevo_vinculo' AND atendido_en IS NULL""",
                             [x["participante_id"], vig["id"]])
        # Si volvió a vincularse, el aviso de desvinculación ya no hace falta.
        get_db().execute(f"""UPDATE aviso_carga SET atendido_en = {AHORA} WHERE participante_id = ?
                             AND tipo = 'desvinculado' AND atendido_en IS NULL""", [x["participante_id"]])


def pendientes(pid: int) -> list[dict]:
    return get_db().q(
        """SELECT a.*, u.nombres, u.apellidos, v.fecha_inicio, v.fecha_fin FROM aviso_carga a
           JOIN proyecto_participante pp ON pp.id = a.participante_id JOIN usuario u ON u.id = pp.investigador_id
           JOIN vinculo v ON v.id = a.vinculo_id
           WHERE a.proyecto_id = ? AND a.atendido_en IS NULL ORDER BY a.creado_en, a.id""", [pid])


def n_pendientes(pid: int) -> int:
    return get_db().q("SELECT COUNT(*) n FROM aviso_carga WHERE proyecto_id = ? AND atendido_en IS NULL",
                      [pid])[0]["n"]


def atender(pid: int, aviso_id: int, por: int) -> bool:
    cur = get_db().q("SELECT id FROM aviso_carga WHERE id = ? AND proyecto_id = ? AND atendido_en IS NULL",
                     [aviso_id, pid])
    if cur:
        get_db().execute(f"UPDATE aviso_carga SET atendido_en = {AHORA}, atendido_por = ? WHERE id = ?", [por, aviso_id])
    return bool(cur)


vinculos.OYENTES.append(revisar)
