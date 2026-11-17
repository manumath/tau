"""Equivalencias entre el plan nuevo (en elaboración) y los planes que reemplaza (PLAN §65, etapa 5).

Como el catálogo de asignaturas es común, una asignatura que está en los dos planes es equivalente por sí sola. Solo se
registran los grupos que cambian: varias asignaturas del plan anterior equivalen a varias del nuevo.
"""
from app.academico import planes
from app.comun.db import auditar, get_db, transaccion

OBLIGATORIAS = ("obligatoria", "trabajo_final")


def _asignaturas(pid: int) -> dict[int, dict]:
    return {f["asignatura_id"]: f for f in planes.asignaturas(pid) if f["asignatura_id"] is not None}


def origenes_posibles(pid: int) -> list[dict]:
    """Planes que el nuevo puede reemplazar: los que no son borradores, el vigente de su programa primero."""
    return get_db().q(
        """SELECT p.id, p.nombre, p.estado, pr.nombre AS programa FROM plan_estudios p
           JOIN programa pr ON pr.id = p.programa_id WHERE p.estado <> 'elaboracion' AND p.id <> ?
           ORDER BY p.programa_id = (SELECT programa_id FROM plan_estudios WHERE id = ?) DESC,
                    p.estado = 'vigente' DESC, p.vigente_desde DESC, pr.nombre""", [pid, pid])


def anterior(pid: int) -> dict | None:
    """El plan que este reemplaza por omisión: el vigente (o en cierre) de su programa."""
    f = get_db().q("""SELECT p.id FROM plan_estudios p WHERE p.programa_id = (SELECT programa_id FROM plan_estudios WHERE id = ?)
                      AND p.id <> ? AND p.estado IN ('vigente', 'cierre')
                      ORDER BY p.estado = 'vigente' DESC, p.vigente_desde DESC LIMIT 1""", [pid, pid])
    return planes.obtener(f[0]["id"]) if f else None


def grupos(origen: int, destino: int) -> list[dict]:
    res = []
    for e in get_db().q("SELECT * FROM equivalencia WHERE plan_origen_id = ? AND plan_destino_id = ? ORDER BY id",
                        [origen, destino]):
        items = get_db().q("""SELECT i.lado, a.id, a.sigla, a.nombre FROM equivalencia_item i
                              JOIN asignatura a ON a.id = i.asignatura_id WHERE i.equivalencia_id = ? ORDER BY a.sigla""",
                           [e["id"]])
        e["origen"] = [i for i in items if i["lado"] == "origen"]
        e["destino"] = [i for i in items if i["lado"] == "destino"]
        res.append(e)
    return res


def brechas(origen: int, destino: int) -> dict:
    """Cómo queda cada asignatura del plan anterior frente al nuevo.
    → {'filas': [{fila, estado: 'igual'|'equivalente'|'sin', destino: [siglas]}], 'nuevas': [filas del nuevo sin origen],
       'sin_obligatorias': n}."""
    o, d = _asignaturas(origen), _asignaturas(destino)
    gs = grupos(origen, destino)
    cubre = {}
    for g in gs:
        for a in g["origen"]:
            cubre[a["id"]] = [x["sigla"] for x in g["destino"]]
    cubiertas_destino = {a["id"] for g in gs for a in g["destino"]}
    filas = []
    for aid, f in o.items():
        if aid in d:
            filas.append({"fila": f, "estado": "igual", "destino": [f["sigla"]]})
        elif aid in cubre:
            filas.append({"fila": f, "estado": "equivalente", "destino": cubre[aid]})
        else:
            filas.append({"fila": f, "estado": "sin", "destino": []})
    nuevas = [f for aid, f in d.items() if aid not in o and aid not in cubiertas_destino]
    return {"filas": filas, "nuevas": nuevas, "grupos": gs,
            "sin_obligatorias": sum(r["estado"] == "sin" and r["fila"]["tipo"] in OBLIGATORIAS for r in filas)}


def crear(origen: int, destino: int, origen_ids: list[int], destino_ids: list[int], nota: str, uid: int) -> list[str]:
    po, pd = planes.obtener(origen), planes.obtener(destino)
    if not pd or pd["estado"] != "elaboracion":
        return ["Las equivalencias se registran desde un plan en elaboración."]
    if not po or po["estado"] == "elaboracion" or origen == destino:
        return ["Elija el plan que este reemplaza."]
    nota = (nota or "").strip()
    errores = []
    if len(nota) > 500:
        errores.append("La nota admite hasta 500 caracteres.")
    o, d = _asignaturas(origen), _asignaturas(destino)
    origen_ids, destino_ids = sorted(set(origen_ids)), sorted(set(destino_ids))
    if not origen_ids or not destino_ids:
        errores.append("Marque al menos una asignatura del plan anterior y una del nuevo.")
    if any(a not in o for a in origen_ids) or any(a not in d for a in destino_ids):
        errores.append("Una asignatura no pertenece al plan indicado.")
    if set(origen_ids) & set(d):
        errores.append("Una asignatura del plan anterior ya está en el nuevo: es equivalente por su sigla.")
    usadas = {(i["lado"], i["asignatura_id"]) for g in get_db().q(
        "SELECT id FROM equivalencia WHERE plan_origen_id = ? AND plan_destino_id = ?", [origen, destino])
        for i in get_db().q("SELECT lado, asignatura_id FROM equivalencia_item WHERE equivalencia_id = ?", [g["id"]])}
    if any(("origen", a) in usadas for a in origen_ids) or any(("destino", a) in usadas for a in destino_ids):
        errores.append("Una de las asignaturas ya está en otra equivalencia entre estos dos planes.")
    if errores:
        return errores
    with transaccion():
        eid = get_db().t.equivalencia.insert(plan_origen_id=origen, plan_destino_id=destino, nota=nota or None,
                                             creado_por=uid)["id"]
        for a in origen_ids:
            get_db().t.equivalencia_item.insert(equivalencia_id=eid, lado="origen", asignatura_id=a)
        for a in destino_ids:
            get_db().t.equivalencia_item.insert(equivalencia_id=eid, lado="destino", asignatura_id=a)
        auditar(uid, "editar_equivalencias_plan", "plan_estudios", destino,
                f"{', '.join(o[a]['sigla'] for a in origen_ids)} ≡ {', '.join(d[a]['sigla'] for a in destino_ids)}")
    return []


def eliminar(destino: int, eid: int, uid: int) -> bool:
    e = get_db().q("SELECT * FROM equivalencia WHERE id = ? AND plan_destino_id = ?", [eid, destino])
    pd = planes.obtener(destino)
    if not e or not pd or pd["estado"] != "elaboracion":
        return False
    with transaccion():
        get_db().execute("DELETE FROM equivalencia WHERE id = ?", [eid])
        auditar(uid, "editar_equivalencias_plan", "plan_estudios", destino, "Quitó una equivalencia")
    return True


def verificar(pid: int) -> dict | None:
    """Aviso de la lista de verificación: obligatorias del plan anterior que el nuevo no cubre (None si no reemplaza a
    ningún plan)."""
    ant = anterior(pid)
    if not ant:
        return None
    b = brechas(ant["id"], pid)
    sin = [r["fila"]["sigla"] for r in b["filas"] if r["estado"] == "sin" and r["fila"]["tipo"] in OBLIGATORIAS]
    return {"clave": "equivalencias", "texto": f"Cada obligatoria de {ant['programa']} · {ant['nombre']} tiene equivalente",
            "nivel": "aviso" if sin else "ok",
            "detalle": f"Sin equivalente: {', '.join(sin[:8])}{'…' if len(sin) > 8 else ''}." if sin else ""}
