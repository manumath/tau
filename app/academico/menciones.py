"""Menciones de un plan en elaboración (PLAN §65, etapa 4): itinerarios con asignaturas propias y mínimos."""
from app.academico import planes
from app.comun.db import auditar, get_db, transaccion


def medida(fila: dict, plan: dict) -> int:
    """Lo que aporta una asignatura al mínimo de la mención: créditos, o horas del semestre completo en un plan por horas
    (horas semanales por las semanas del semestre)."""
    if plan["sistema"] == "creditos":
        return fila["creditos"] or 0
    semanal = (fila["horas_teoricas"] or 0) + (fila["horas_practicas"] or 0) + (fila["horas_laboratorio"] or 0)
    return semanal * (plan["semanas_semestre"] or 0)


def listar(pid: int) -> list[dict]:
    """Menciones del plan con sus asignaturas propias, cuántas son y cuánto suman."""
    plan = planes.obtener(pid)
    res = []
    for m in get_db().q("SELECT * FROM mencion WHERE plan_id = ? ORDER BY id", [pid]):
        filas = get_db().q(
            """SELECT pa.*, a.sigla, a.nombre AS asignatura, ma.obligatoria FROM mencion_asignatura ma
               JOIN plan_asignatura pa ON pa.id = ma.plan_asignatura_id LEFT JOIN asignatura a ON a.id = pa.asignatura_id
               WHERE ma.mencion_id = ? ORDER BY COALESCE(pa.semestre, 99), pa.orden""", [m["id"]])
        m["asignaturas"] = filas
        m["n"] = len(filas)
        m["total_medida"] = sum(medida(f, plan) for f in filas)
        res.append(m)
    return res


def obtener(mid: int) -> dict | None:
    f = get_db().q("SELECT * FROM mencion WHERE id = ?", [mid])
    return f[0] if f else None


def de_las_filas(pid: int) -> dict[int, list[str]]:
    """{plan_asignatura_id: [nombres de sus menciones]} para marcarlas en la malla."""
    res: dict = {}
    for r in get_db().q("""SELECT ma.plan_asignatura_id, m.nombre FROM mencion_asignatura ma
                           JOIN mencion m ON m.id = ma.mencion_id WHERE m.plan_id = ? ORDER BY m.id""", [pid]):
        res.setdefault(r["plan_asignatura_id"], []).append(r["nombre"])
    return res


def _entero(texto, etiqueta, errores, minimo, maximo):
    texto = (texto or "").strip()
    if not texto:
        return None
    if not texto.isdigit() or not minimo <= int(texto) <= maximo:
        errores.append(f"{etiqueta}: debe ser un número entre {minimo} y {maximo}.")
        return None
    return int(texto)


def guardar(pid: int, mid: int | None, f: dict, uid: int) -> list[str]:
    plan = planes.obtener(pid)
    if not plan or plan["estado"] != "elaboracion":
        return ["Solo se editan las menciones de un plan en elaboración."]
    actual = obtener(mid) if mid else None
    if mid and (not actual or actual["plan_id"] != pid):
        return ["La mención no está en este plan."]
    errores = []
    nombre = (f.get("nombre") or "").strip()
    if not nombre or len(nombre) > 100:
        errores.append("El nombre de la mención es obligatorio (hasta 100 caracteres).")
    elif get_db().q("SELECT 1 FROM mencion WHERE plan_id = ? AND nombre = ? AND id <> ?", [pid, nombre, mid or 0]):
        errores.append(f"El plan ya tiene una mención llamada «{nombre}».")
    descripcion = (f.get("descripcion") or "").strip()
    if len(descripcion) > 1000:
        errores.append("La descripción admite hasta 1.000 caracteres.")
    duracion = plan["duracion_semestres"] or 20
    eleccion = _entero(f.get("semestre_eleccion"), "Semestre de elección", errores, 1, duracion)
    min_asig = _entero(f.get("minimo_asignaturas"), "Mínimo de asignaturas", errores, 0, 200)
    min_medida = _entero(f.get("minimo_medida"), "Mínimo de créditos u horas", errores, 0, 100_000)
    if errores:
        return errores
    valores = dict(nombre=nombre, descripcion=descripcion or None, semestre_eleccion=eleccion,
                   minimo_asignaturas=min_asig, minimo_medida=min_medida)
    with transaccion():
        if mid:
            get_db().t.mencion.update(id=mid, **valores)
        else:
            mid = get_db().t.mencion.insert(plan_id=pid, **valores)["id"]
        auditar(uid, "editar_mencion_plan", "plan_estudios", pid, f"{'Modificó' if actual else 'Agregó'} la mención {nombre}")
    return []


def eliminar(pid: int, mid: int, uid: int) -> bool:
    plan, m = planes.obtener(pid), obtener(mid)
    if not plan or plan["estado"] != "elaboracion" or not m or m["plan_id"] != pid:
        return False
    with transaccion():
        get_db().execute("DELETE FROM mencion WHERE id = ?", [mid])
        auditar(uid, "editar_mencion_plan", "plan_estudios", pid, f"Quitó la mención {m['nombre']}")
    return True


def asignar(pid: int, mid: int, seleccion: dict[int, str], uid: int) -> list[str]:
    """Reemplaza las asignaturas de la mención. `seleccion`: {plan_asignatura_id: 'o' (obligatoria) | 'p' (optativa)}."""
    plan, m = planes.obtener(pid), obtener(mid)
    if not plan or plan["estado"] != "elaboracion" or not m or m["plan_id"] != pid:
        return ["Solo se editan las menciones de un plan en elaboración."]
    propias = {r["id"] for r in get_db().q("SELECT id FROM plan_asignatura WHERE plan_id = ? AND asignatura_id IS NOT NULL",
                                          [pid])}
    elegidas = {k: v for k, v in seleccion.items() if v in ("o", "p") and k in propias}
    with transaccion():
        get_db().execute("DELETE FROM mencion_asignatura WHERE mencion_id = ?", [mid])
        for k, v in elegidas.items():
            get_db().t.mencion_asignatura.insert(mencion_id=mid, plan_asignatura_id=k, obligatoria=int(v == "o"))
        auditar(uid, "editar_mencion_plan", "plan_estudios", pid, f"{m['nombre']}: {len(elegidas)} asignatura(s)")
    return []


def copiar(origen: int, destino: int, mapa: dict[int, int]) -> None:
    """Copia las menciones de un plan a otro; `mapa`: {plan_asignatura_id viejo: nuevo}."""
    for m in get_db().q("SELECT * FROM mencion WHERE plan_id = ?", [origen]):
        nueva = get_db().t.mencion.insert(plan_id=destino, nombre=m["nombre"], descripcion=m["descripcion"],
                                          semestre_eleccion=m["semestre_eleccion"],
                                          minimo_asignaturas=m["minimo_asignaturas"], minimo_medida=m["minimo_medida"])["id"]
        for ma in get_db().q("SELECT * FROM mencion_asignatura WHERE mencion_id = ?", [m["id"]]):
            if ma["plan_asignatura_id"] in mapa:
                get_db().t.mencion_asignatura.insert(mencion_id=nueva, plan_asignatura_id=mapa[ma["plan_asignatura_id"]],
                                                     obligatoria=ma["obligatoria"])


def verificar(pid: int) -> dict | None:
    """Punto de la lista de verificación: lo que falta en cada mención (o None si no hay menciones)."""
    ms = listar(pid)
    if not ms:
        return None
    plan = planes.obtener(pid)
    unidad = "créditos" if plan["sistema"] == "creditos" else "horas"
    problemas = []
    for m in ms:
        if not m["n"]:
            problemas.append(f"{m['nombre']}: no tiene asignaturas")
            continue
        if m["minimo_asignaturas"] and m["n"] < m["minimo_asignaturas"]:
            problemas.append(f"{m['nombre']}: pide {m['minimo_asignaturas']} asignaturas y tiene {m['n']}")
        if m["minimo_medida"] and m["total_medida"] < m["minimo_medida"]:
            problemas.append(f"{m['nombre']}: pide {m['minimo_medida']} {unidad} y suma {m['total_medida']}")
    return {"clave": "menciones", "texto": "Cada mención tiene sus asignaturas y cumple su mínimo",
            "nivel": "falta" if problemas else "ok", "detalle": "; ".join(problemas[:4])}
