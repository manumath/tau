"""Ciclo de vida de un plan: poner en vigencia, iniciar su cierre y cerrarlo (PLAN §65, etapa 5).

en elaboración → vigente → en proceso de cierre → cerrado. Solo la Dirección de Carrera decide (`decidir_planes`); las
rutas lo comprueban. Cada programa tiene a lo sumo un plan vigente: al poner en vigencia el nuevo, el vigente del mismo
programa pasa a «en proceso de cierre» con el último ingreso en el año anterior al del plan nuevo.
"""
from app.academico import malla, planes
from app.comun.db import AHORA, auditar, get_db, transaccion


def estudiantes_en(pid: int) -> int:
    """Estudiantes de ese plan que siguen cursando (o con la matrícula congelada)."""
    return get_db().q("SELECT COUNT(*) n FROM estudiante WHERE plan_id = ? AND estado IN ('cursando', 'congelado')",
                      [pid])[0]["n"]


def faltantes(pid: int) -> list[str]:
    return [v["texto"] + (f": {v['detalle']}" if v["detalle"] else "") for v in malla.verificar(pid) if v["nivel"] == "falta"]


def _activar(p: dict, uid: int) -> None:
    db = get_db()
    vigente = db.q("SELECT * FROM plan_estudios WHERE programa_id = ? AND estado = 'vigente' AND id <> ?",
                   [p["programa_id"], p["id"]])
    for v in vigente:
        ultimo = max(v["vigente_desde"], p["vigente_desde"] - 1)
        db.execute(f"""UPDATE plan_estudios SET estado = 'cierre', vigente_hasta = ?, cierre_en = {AHORA}, cierre_por = ?,
                       motivo_cierre = ? WHERE id = ?""",
                   [ultimo, uid, f"Reemplazado por el plan {p['nombre']}.", v["id"]])
        auditar(uid, "iniciar_cierre_plan", "plan_estudios", v["id"], f"{p['programa']} · {v['nombre']}: reemplazado por "
                                                                       f"{p['nombre']} (último ingreso {ultimo})")
    db.execute(f"UPDATE plan_estudios SET estado = 'vigente', vigente_hasta = NULL, en_vigencia_en = {AHORA}, "
               "en_vigencia_por = ? WHERE id = ?", [uid, p["id"]])
    auditar(uid, "poner_plan_en_vigencia", "plan_estudios", p["id"], f"{p['programa']} · {p['nombre']}")


def poner_en_vigencia(pid: int, uid: int) -> list[str]:
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return ["Solo se pone en vigencia un plan en elaboración."]
    falta = faltantes(pid)
    if falta:
        return [f"Todavía falta: {x}" for x in falta]
    with transaccion():
        _activar(p, uid)
    return []


def programas_que_cierran(rid: int) -> list[dict]:
    """Planes vigentes de programas que no tienen plan en la reforma: el programa desaparece y su plan pasa a cierre."""
    return get_db().q(
        """SELECT p.id FROM plan_estudios p WHERE p.estado = 'vigente' AND p.programa_id NOT IN
           (SELECT programa_id FROM plan_estudios WHERE reforma_id = ?)""", [rid])


def poner_reforma_en_vigencia(rid: int, uid: int) -> list[str]:
    """Pone en vigencia todos los planes en elaboración de la reforma, o ninguno. Los programas que no tienen plan en la
    reforma desaparecen: su plan vigente pasa a «en proceso de cierre» (decisión del 13-nov-2026)."""
    borradores = [planes.obtener(f["id"]) for f in get_db().q(
        "SELECT id FROM plan_estudios WHERE reforma_id = ? AND estado = 'elaboracion' ORDER BY id", [rid])]
    if not borradores:
        return ["La reforma no tiene planes en elaboración."]
    errores = [f"{p['programa']} · {p['nombre']}: {x}" for p in borradores for x in faltantes(p["id"])]
    if errores:
        return errores
    reforma = get_db().q("SELECT * FROM reforma_curricular WHERE id = ?", [rid])[0]
    desaparecen = [planes.obtener(f["id"]) for f in programas_que_cierran(rid)]
    with transaccion():
        for p in borradores:
            _activar(p, uid)
        for v in desaparecen:
            ultimo = max(v["vigente_desde"], reforma["vigente_desde"] - 1)
            get_db().execute(f"""UPDATE plan_estudios SET estado = 'cierre', vigente_hasta = ?, cierre_en = {AHORA},
                                 cierre_por = ?, motivo_cierre = ? WHERE id = ?""",
                             [ultimo, uid, f"El programa no continúa en la reforma {reforma['nombre']}.", v["id"]])
            auditar(uid, "iniciar_cierre_plan", "plan_estudios", v["id"],
                    f"{v['programa']} · {v['nombre']}: el programa no continúa en la reforma {reforma['nombre']} "
                    f"(último ingreso {ultimo})")
    return []


def iniciar_cierre(pid: int, anio: str, motivo: str, uid: int) -> list[str]:
    p = planes.obtener(pid)
    if not p or p["estado"] != "vigente":
        return ["Solo se inicia el cierre de un plan vigente."]
    errores = []
    anio = (anio or "").strip()
    if not anio.isdigit() or not p["vigente_desde"] <= int(anio) <= 2100:
        errores.append(f"El año del último ingreso debe estar entre {p['vigente_desde']} y 2100.")
    motivo = (motivo or "").strip()
    if not motivo or len(motivo) > 500:
        errores.append("Indique la resolución o el motivo del cierre (hasta 500 caracteres).")
    if errores:
        return errores
    with transaccion():
        get_db().execute(f"""UPDATE plan_estudios SET estado = 'cierre', vigente_hasta = ?, cierre_en = {AHORA},
                             cierre_por = ?, motivo_cierre = ? WHERE id = ?""", [int(anio), uid, motivo, pid])
        auditar(uid, "iniciar_cierre_plan", "plan_estudios", pid, f"{p['programa']} · {p['nombre']}: último ingreso {anio}")
    return []


def cerrar(pid: int, motivo: str, forzar: bool, uid: int) -> list[str]:
    p = planes.obtener(pid)
    if not p or p["estado"] != "cierre":
        return ["Solo se cierra un plan en proceso de cierre."]
    motivo = (motivo or "").strip()
    quedan = estudiantes_en(pid)
    errores = []
    if quedan and not forzar:
        errores.append(f"Quedan {quedan} estudiantes cursando en este plan. Si de todos modos se cierra, marque la casilla "
                       "e indique el motivo.")
    if (quedan or forzar) and not motivo:
        errores.append("Indique el motivo del cierre.")
    if len(motivo) > 500:
        errores.append("El motivo admite hasta 500 caracteres.")
    if errores:
        return errores
    previo = p["motivo_cierre"] or ""
    with transaccion():
        get_db().execute(f"""UPDATE plan_estudios SET estado = 'cerrado', cerrado_en = {AHORA}, cerrado_por = ?,
                             motivo_cierre = ? WHERE id = ?""",
                         [uid, " · ".join(x for x in (previo, f"Cierre: {motivo}" if motivo else "") if x) or None, pid])
        auditar(uid, "cerrar_plan", "plan_estudios", pid,
                f"{p['programa']} · {p['nombre']}" + (f" con {quedan} estudiantes cursando" if quedan else ""))
    return []
