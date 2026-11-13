"""Consultas de los planes de estudio (catálogo curricular, PLAN.md sección 24)."""
from app.academico import importar_planes
from app.comun import permisos
from app.comun.db import AHORA, auditar, get_db, transaccion

NIVELES = {"licenciatura": "Licenciatura", "maestria": "Maestría", "doctorado": "Doctorado",
           "especialidad": "Especialidad", "diplomado": "Diplomado"}
TIPOS = {"obligatoria": "Obligatoria", "trabajo_final": "Trabajo final", "electiva": "Electiva",
         "electiva_a": "Electiva A", "electiva_b": "Electiva B", "casilla_electiva": "Electiva",
         "casilla_electiva_a": "Electiva A", "casilla_electiva_b": "Electiva B"}
GRUPOS_ELECTIVAS = {"electiva_a": "Electivas A", "electiva_b": "Electivas B", "electiva": "Electivas"}
ORDINALES = ["", "Primer", "Segundo", "Tercer", "Cuarto", "Quinto", "Sexto", "Séptimo", "Octavo", "Noveno",
             "Décimo"]


# Ciclo de vida de un plan (PLAN §65): un borrador solo lo ven quienes elaboran planes.
ESTADOS = {"elaboracion": "En elaboración", "vigente": "Vigente", "cierre": "En proceso de cierre",
           "cerrado": "Cerrado"}
TONOS_ESTADO = {"elaboracion": "azul", "vigente": "verde", "cierre": "ambar", "cerrado": "gris"}
ICONOS_ESTADO = {"elaboracion": "pencil", "vigente": "check", "cierre": "hourglass", "cerrado": "lock"}


def puede_elaborar(auth) -> bool:
    return permisos.puede(auth, "elaborar_planes")


def puede_ver(plan: dict, auth) -> bool:
    """Los borradores solo los ven la Dirección de Carrera y la Coordinación académica."""
    return plan["estado"] != "elaboracion" or puede_elaborar(auth)


def listar(auth=None, estado: str | None = None) -> list[dict]:
    """Planes que `auth` puede ver (sin `auth`, solo los que ve todo el mundo), por programa; con `estado`, solo
    los de ese estado."""
    filas = get_db().q(
        """SELECT p.*, pr.nombre AS programa, pr.nivel, r.nombre AS reforma, r.resolucion AS reforma_resolucion,
                  (SELECT COUNT(*) FROM plan_asignatura WHERE plan_id = p.id AND asignatura_id IS NOT NULL) AS n_asignaturas,
                  (SELECT COUNT(*) FROM observacion_plan WHERE plan_id = p.id AND estado = 'pendiente') AS n_pendientes
           FROM plan_estudios p JOIN programa pr ON pr.id = p.programa_id
           LEFT JOIN reforma_curricular r ON r.id = p.reforma_id
           ORDER BY p.vigente_desde DESC, CASE pr.nivel WHEN 'licenciatura' THEN 1 WHEN 'maestria' THEN 2 ELSE 3 END,
                    pr.nombre""")
    return [p for p in filas if puede_ver(p, auth) and (estado is None or p["estado"] == estado)]


def por_reforma(planes_: list[dict]) -> list[tuple[dict, list[dict]]]:
    """[(reforma, planes)] en el orden en que vienen (la reforma más reciente primero)."""
    grupos: dict = {}
    for p in planes_:
        clave = p["reforma_id"]
        grupos.setdefault(clave, ({"nombre": p["reforma"] or p["nombre"], "resolucion": p["reforma_resolucion"],
                                   "vigente_desde": p["vigente_desde"]}, []))[1].append(p)
    return list(grupos.values())


def obtener(pid: int) -> dict | None:
    filas = get_db().q("""SELECT p.*, pr.nombre AS programa, pr.nivel, r.nombre AS reforma
                          FROM plan_estudios p JOIN programa pr ON pr.id = p.programa_id
                          LEFT JOIN reforma_curricular r ON r.id = p.reforma_id WHERE p.id = ?""", [pid])
    return filas[0] if filas else None


def asignaturas(pid: int) -> list[dict]:
    """Asignaturas y casillas del plan, en el orden del documento, con sus requisitos."""
    filas = get_db().q(
        """SELECT pa.*, a.sigla, a.nombre, a.de_la_carrera, a.linea_formativa,
                  ar.nombre AS area, li.nombre AS linea
           FROM plan_asignatura pa LEFT JOIN asignatura a ON a.id = pa.asignatura_id
           LEFT JOIN area_investigacion ar ON ar.id = a.area_id LEFT JOIN linea_investigacion li ON li.id = a.linea_id
           WHERE pa.plan_id = ? ORDER BY pa.orden""", [pid])
    requisitos = {}
    for r in get_db().q("""SELECT r.* FROM requisito r JOIN plan_asignatura pa ON pa.id = r.plan_asignatura_id
                           WHERE pa.plan_id = ? ORDER BY r.id""", [pid]):
        requisitos.setdefault(r["plan_asignatura_id"], []).append("Egresado" if r["condicion"] else r["sigla"])
    for f in filas:
        f["requisitos"] = requisitos.get(f["id"], [])
    return filas


def por_semestre(pid: int) -> list[tuple[int, str | None, list[dict]]]:
    """[(semestre, ciclo, filas)] de las asignaturas y casillas ubicadas en un semestre."""
    res = []
    for f in asignaturas(pid):
        if f["semestre"] is None:
            continue
        if not res or res[-1][0] != f["semestre"]:
            res.append((f["semestre"], f["ciclo"], []))
        res[-1][2].append(f)
    return res


def electivas(pid: int) -> dict[str, list[dict]]:
    """{'electiva_a': [...], ...}: las listas de asignaturas electivas del plan."""
    res = {}
    for f in asignaturas(pid):
        if f["semestre"] is None and f["tipo"] in GRUPOS_ELECTIVAS:
            res.setdefault(f["tipo"], []).append(f)
    return res


def totales(pid: int) -> dict:
    return importar_planes.totales(get_db().conn, pid)


def observaciones(pid: int) -> list[dict]:
    return get_db().q("""SELECT o.*, u.nombres || ' ' || u.apellidos AS resuelta_por_nombre FROM observacion_plan o
                         LEFT JOIN usuario u ON u.id = o.resuelta_por WHERE o.plan_id = ?
                         ORDER BY o.estado = 'resuelta', o.id""", [pid])


def resolver(oid: int, resolucion: str, uid: int) -> str | None:
    resolucion = (resolucion or "").strip()
    if not resolucion:
        return "Indique cómo se resolvió (p. ej., «Confirmado con la Dirección Académica: …»)."
    if len(resolucion) > 1000:
        return "La resolución admite hasta 1.000 caracteres."
    get_db().execute(f"""UPDATE observacion_plan SET estado = 'resuelta', resolucion = ?, resuelta_por = ?,
                         resuelta_en = {AHORA} WHERE id = ?""", [resolucion, uid, oid])
    return None


def observacion(oid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM observacion_plan WHERE id = ?", [oid])
    return filas[0] if filas else None


# --- Edición del borrador (PLAN §65, etapa 2) ------------------------------------------------------------------------

def _entero(texto, minimo, maximo, etiqueta, errores, obligatorio=False):
    texto = (texto or "").strip()
    if not texto:
        if obligatorio:
            errores.append(f"{etiqueta}: escriba un número.")
        return None
    try:
        n = int(texto.replace(".", ""))
        if not minimo <= n <= maximo:
            raise ValueError
        return n
    except ValueError:
        errores.append(f"{etiqueta}: debe ser un número entre {minimo} y {maximo}.")
        return None


def actualizar_datos(pid: int, f: dict, uid: int) -> list[str]:
    """Datos generales de un plan en elaboración (y el título que otorga su programa). → errores."""
    p = obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return ["Solo se pueden editar los datos de un plan en elaboración."]
    errores = []
    nombre = (f.get("nombre") or "").strip()
    if not nombre or len(nombre) > 60:
        errores.append("El nombre del plan es obligatorio (hasta 60 caracteres).")
    elif get_db().q("SELECT 1 FROM plan_estudios WHERE programa_id = ? AND nombre = ? AND id <> ?",
                    [p["programa_id"], nombre, pid]):
        errores.append(f"El programa ya tiene un plan llamado «{nombre}».")
    resolucion = (f.get("resolucion") or "").strip()
    titulo = (f.get("titulo") or "").strip()
    if len(resolucion) > 120 or len(titulo) > 120:
        errores.append("La resolución y el título admiten hasta 120 caracteres.")
    sistema = f.get("sistema")
    if sistema not in ("horas", "creditos"):
        errores.append("Elija cómo se mide el plan: horas o créditos.")
    anio = _entero(f.get("vigente_desde"), reformas_anio_min(), 2100, "Año en que rige", errores, True)
    semanas = _entero(f.get("semanas_semestre"), 1, 60, "Semanas del semestre", errores, sistema == "horas")
    por_credito = _entero(f.get("horas_por_credito"), 1, 200, "Horas por crédito", errores, sistema == "creditos")
    nota = _entero(f.get("nota_minima"), 0, 100, "Nota mínima de aprobación", errores)
    totales_ = {k: _entero(f.get(k), 0, 1_000_000, "Total declarado", errores)
                for k in ("total_teoricas", "total_practicas", "total_laboratorio", "total_creditos")}
    if errores:
        return errores
    get_db().execute(
        """UPDATE plan_estudios SET nombre = ?, resolucion = ?, vigente_desde = ?, sistema = ?, semanas_semestre = ?,
           horas_por_credito = ?, nota_minima = ?, total_teoricas = ?, total_practicas = ?, total_laboratorio = ?,
           total_creditos = ? WHERE id = ?""",
        [nombre, resolucion or None, anio, sistema, semanas if sistema == "horas" else None,
         por_credito if sistema == "creditos" else None, nota, *totales_.values(), pid])
    get_db().execute("UPDATE programa SET titulo = ? WHERE id = ?", [titulo or None, p["programa_id"]])
    auditar(uid, "editar_plan", "plan_estudios", pid, f"{p['programa']} · {nombre}")
    return []


def reformas_anio_min() -> int:
    return 2000


def eliminar_borrador(pid: int, uid: int) -> str | None:
    """Elimina un plan en elaboración con todo lo suyo, y la reforma si se queda sin planes. → error o None."""
    p = obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return "Solo se puede eliminar un plan en elaboración."
    with transaccion():
        get_db().execute("DELETE FROM plan_estudios WHERE id = ?", [pid])
        if p["reforma_id"] and not get_db().q("SELECT 1 FROM plan_estudios WHERE reforma_id = ?", [p["reforma_id"]]):
            get_db().execute("DELETE FROM reforma_curricular WHERE id = ?", [p["reforma_id"]])
        if not get_db().q("SELECT 1 FROM plan_estudios WHERE programa_id = ?", [p["programa_id"]]):
            get_db().execute("DELETE FROM programa WHERE id = ?", [p["programa_id"]])
        auditar(uid, "eliminar_plan", "plan_estudios", pid, f"{p['programa']} · {p['nombre']} (en elaboración)")
    return None
