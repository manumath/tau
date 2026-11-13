"""Reformas curriculares: crear una con sus planes en elaboración (PLAN §65, etapa 2).

Una reforma agrupa los planes de sus programas (hoy dos licenciaturas y dos maestrías terminales; la próxima puede
traer uno, dos o tres). Cada programa de la reforma vigente se continúa copiando su plan, se empieza vacío o no
continúa; además se pueden agregar programas nuevos. Todos los planes nacen en elaboración.
"""
from app.academico import planes
from app.comun import unidades
from app.comun.db import auditar, get_db, transaccion

ANIO_MIN, ANIO_MAX = 2000, 2100
CAMPOS_PLAN = ("tipo", "semestre", "ciclo", "horas_teoricas", "horas_practicas", "horas_laboratorio", "creditos")


def programas_con_plan() -> list[dict]:
    """Programas con el plan que se copiaría al continuarlos: el vigente o, si no hay, el que está en proceso de
    cierre más reciente. Los que solo tienen planes cerrados o borradores no aparecen."""
    res = []
    for pr in get_db().q("SELECT * FROM programa ORDER BY CASE nivel WHEN 'licenciatura' THEN 1 WHEN 'maestria' THEN 2 "
                         "ELSE 3 END, nombre"):
        plan = get_db().q(
            """SELECT p.*, (SELECT COUNT(*) FROM plan_asignatura WHERE plan_id = p.id AND asignatura_id IS NOT NULL)
                          AS n_asignaturas FROM plan_estudios p
               WHERE p.programa_id = ? AND p.estado IN ('vigente', 'cierre')
               ORDER BY p.estado = 'vigente' DESC, p.vigente_desde DESC LIMIT 1""", [pr["id"]])
        if plan:
            res.append({**pr, "plan": plan[0]})
    return res


def copiar_plan(origen: int, programa_id: int, nombre: str, reforma_id: int, anio: int, resolucion: str | None) -> int:
    """Crea en elaboración un plan con las asignaturas, casillas, electivas y requisitos de `origen`. Los totales
    declarados quedan vacíos (son los del documento del plan nuevo) y no se copian las observaciones."""
    db = get_db()
    o = db.q("SELECT * FROM plan_estudios WHERE id = ?", [origen])[0]
    nuevo = crear_plan(programa_id, nombre, reforma_id, anio, resolucion, o["sistema"], o["semanas_semestre"],
                       o["horas_por_credito"], o["nota_minima"], o["duracion_semestres"])
    for c in db.q("SELECT nombre, semestre_desde, semestre_hasta FROM plan_ciclo WHERE plan_id = ?", [origen]):
        db.t.plan_ciclo.insert(plan_id=nuevo, **c)
    for pa in db.q("SELECT * FROM plan_asignatura WHERE plan_id = ? ORDER BY orden, id", [origen]):
        pid = db.t.plan_asignatura.insert(plan_id=nuevo, asignatura_id=pa["asignatura_id"], orden=pa["orden"],
                                          **{c: pa[c] for c in CAMPOS_PLAN})["id"]
        for r in db.q("SELECT sigla, condicion FROM requisito WHERE plan_asignatura_id = ?", [pa["id"]]):
            db.t.requisito.insert(plan_asignatura_id=pid, sigla=r["sigla"], condicion=r["condicion"])
    return nuevo


def crear_plan(programa_id: int, nombre: str, reforma_id: int, anio: int, resolucion: str | None, sistema="horas",
               semanas=None, horas_credito=None, nota_minima=None, duracion=None) -> int:
    return get_db().t.plan_estudios.insert(
        programa_id=programa_id, nombre=nombre, resolucion=resolucion or None, vigente_desde=anio, sistema=sistema,
        semanas_semestre=semanas, horas_por_credito=horas_credito, nota_minima=nota_minima, estado="elaboracion",
        reforma_id=reforma_id, duracion_semestres=duracion)["id"]


def crear(uid: int, nombre: str, resolucion: str, anio: str, continuar: dict[int, str], nuevos: list[dict]
          ) -> tuple[int | None, list[str]]:
    """Crea la reforma y sus planes en elaboración. `continuar`: {programa_id: 'copia' | 'vacio' | 'no'}. `nuevos`:
    [{nombre, nivel, titulo, sistema, inicio}] con `inicio` = '' o 'vacio' (plan vacío) o el id de un plan a copiar.
    → (id de la reforma, errores)."""
    db = get_db()
    errores = []
    nombre, resolucion = (nombre or "").strip(), (resolucion or "").strip()
    if not nombre:
        errores.append("Escriba el nombre de la reforma (por ejemplo, «Plan 2027»).")
    elif len(nombre) > 60:
        errores.append("El nombre de la reforma admite hasta 60 caracteres.")
    elif db.q("SELECT 1 FROM reforma_curricular WHERE nombre = ?", [nombre]):
        errores.append(f"Ya existe una reforma llamada «{nombre}».")
    if len(resolucion) > 120:
        errores.append("La resolución admite hasta 120 caracteres.")
    try:
        anio_n = int(anio)
        if not ANIO_MIN <= anio_n <= ANIO_MAX:
            raise ValueError
    except (TypeError, ValueError):
        anio_n = None
        errores.append(f"El año en que rige debe estar entre {ANIO_MIN} y {ANIO_MAX}.")
    programas = {p["id"]: p for p in programas_con_plan()}
    elegidos = [(programas[i], modo) for i, modo in continuar.items() if i in programas and modo in ("copia", "vacio")]
    nuevos = [n for n in nuevos if any((n.get("nombre") or "", n.get("titulo") or ""))]
    existentes = {p["nombre"].lower() for p in db.q("SELECT nombre FROM programa")}
    vistos = set()
    for n in nuevos:
        n["nombre"] = (n.get("nombre") or "").strip()
        if not n["nombre"]:
            errores.append("Un programa nuevo necesita su nombre.")
        elif n["nombre"].lower() in existentes | vistos:
            errores.append(f"Ya existe un programa llamado «{n['nombre']}»: elíjalo arriba para continuarlo.")
        vistos.add(n["nombre"].lower())
        if n.get("nivel") not in planes.NIVELES:
            errores.append(f"Elija el nivel de «{n['nombre'] or 'el programa nuevo'}».")
        if len(n.get("titulo") or "") > 120:
            errores.append("El título que otorga admite hasta 120 caracteres.")
    if not elegidos and not nuevos:
        errores.append("La reforma necesita al menos un plan: continúe un programa o agregue uno nuevo.")
    if errores:
        return None, errores
    with transaccion():
        rid = db.t.reforma_curricular.insert(nombre=nombre, resolucion=resolucion or None, vigente_desde=anio_n,
                                             creado_por=uid)["id"]
        for pr, modo in elegidos:
            origen = pr["plan"]
            if modo == "copia":
                copiar_plan(origen["id"], pr["id"], nombre, rid, anio_n, resolucion)
            else:
                vacio = crear_plan(pr["id"], nombre, rid, anio_n, resolucion, origen["sistema"],
                                   origen["semanas_semestre"], origen["horas_por_credito"], origen["nota_minima"],
                                   origen["duracion_semestres"])
                for c in db.q("SELECT nombre, semestre_desde, semestre_hasta FROM plan_ciclo WHERE plan_id = ?",
                              [origen["id"]]):
                    db.t.plan_ciclo.insert(plan_id=vacio, **c)
        for n in nuevos:
            prid = db.t.programa.insert(nombre=n["nombre"], nivel=n["nivel"], titulo=(n.get("titulo") or "").strip() or None,
                                        unidad_id=unidades.id_de("CMAT"))["id"]
            origen = str(n.get("inicio") or "")
            if origen.isdigit() and db.q("SELECT 1 FROM plan_estudios WHERE id = ?", [int(origen)]):
                copiar_plan(int(origen), prid, nombre, rid, anio_n, resolucion)
            else:
                sistema = n.get("sistema") if n.get("sistema") in ("horas", "creditos") else "horas"
                crear_plan(prid, nombre, rid, anio_n, resolucion, sistema, 20 if sistema == "horas" else None)
        auditar(uid, "crear_reforma", "reforma_curricular", rid,
                f"{nombre}: {len(elegidos) + len(nuevos)} plan(es) en elaboración")
    return rid, []
