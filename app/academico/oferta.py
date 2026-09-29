"""Oferta de asignaturas por gestión y asignación docente (PLAN.md, sección 24, paso 3.3).

- Solo se ofertan asignaturas de la Carrera (las de otras carreras las dicta otra unidad).
- Una oferta es una asignatura en una gestión y un paralelo; sirve a todos los planes que la
  incluyen. Cada paralelo tiene uno o más docentes, titular o auxiliar.
- Carga horaria (app.academico.carga): cada materia de un titular en un semestre (grado o maestría)
  son 32 h/mes. Los auxiliares y los cursos de verano e invierno no suman a la carga.
- Los cursos de verano e invierno solo los dictan docentes titulares (de planta); los interinos
  tienen contratos por semestre.
- Asignar a alguien sin vínculo vigente con la Carrera en la gestión no se impide: se avisa.
- Al crear las gestiones de un año, los semestres (I y II) se ofertan con las troncales de las
  licenciaturas (paralelo A, sin docente); las electivas se agregan a mano y una troncal se puede
  quitar (por ejemplo, si se cierra por falta de inscritos).
"""
import re

from app.comun import vinculos
from app.comun.db import get_db

ROLES = {"titular": "Titular", "auxiliar": "Auxiliar"}
HORAS_POR_MATERIA = 32   # h/mes de carga por materia asignada (titular, semestre I o II)
TEMPORADA = ("INV", "VER")


def asignaturas_ofertables() -> list[dict]:
    return get_db().q("SELECT * FROM asignatura WHERE de_la_carrera = 1 ORDER BY sigla")


def troncales(anio: int) -> list[dict]:
    """Asignaturas obligatorias (y el trabajo final) de la Carrera en los planes de licenciatura que
    tienen estudiantes en el año: desde su primer ingreso hasta que egrese el último (último ingreso
    + la duración del plan)."""
    return get_db().q(
        """SELECT DISTINCT a.* FROM plan_asignatura pa JOIN asignatura a ON a.id = pa.asignatura_id
           JOIN plan_estudios p ON p.id = pa.plan_id JOIN programa pr ON pr.id = p.programa_id
           WHERE pr.nivel = 'licenciatura' AND pa.tipo IN ('obligatoria', 'trabajo_final') AND a.de_la_carrera = 1
             AND p.vigente_desde <= :anio
             AND (p.vigente_hasta IS NULL OR :anio <= p.vigente_hasta
                  + (SELECT (MAX(semestre) + 1) / 2 FROM plan_asignatura WHERE plan_id = p.id))
           ORDER BY a.sigla""", {"anio": anio})


def ofertar_troncales(gestion: dict, uid: int) -> int:
    """Agrega a la oferta del semestre las troncales que aún no están (en ningún paralelo), en el
    paralelo A. En los cursos de temporada no hace nada. → cuántas agregó."""
    if gestion["tipo"] in TEMPORADA:
        return 0
    ya = {f["asignatura_id"] for f in get_db().q("SELECT asignatura_id FROM oferta WHERE gestion_id = ?", [gestion["id"]])}
    n = 0
    for a in troncales(gestion["anio"]):
        if a["id"] not in ya:
            get_db().t.oferta.insert(gestion_id=gestion["id"], asignatura_id=a["id"], paralelo="A", creado_por=uid)
            n += 1
    return n


def es_troncal(asignatura_id: int, anio: int) -> bool:
    return any(a["id"] == asignatura_id for a in troncales(anio))


def horas_del_plan(asignatura_id: int) -> int | None:
    """Horas semanales del plan (teóricas + prácticas + laboratorio; si difieren entre planes, la
    mayor), como dato de la asignatura. None si solo está en planes por créditos."""
    fila = get_db().q("""SELECT MAX(COALESCE(horas_teoricas, 0) + COALESCE(horas_practicas, 0)
                                    + COALESCE(horas_laboratorio, 0)) AS h
                         FROM plan_asignatura WHERE asignatura_id = ?""", [asignatura_id])[0]
    return fila["h"] or None


def programas_de(asignatura_id: int) -> list[str]:
    return [f["nombre"] for f in get_db().q(
        """SELECT DISTINCT pr.nombre FROM plan_asignatura pa JOIN plan_estudios p ON p.id = pa.plan_id
           JOIN programa pr ON pr.id = p.programa_id WHERE pa.asignatura_id = ? ORDER BY pr.nombre""", [asignatura_id])]


def listar(gestion_id: int) -> list[dict]:
    filas = get_db().q(
        """SELECT o.*, a.sigla, a.nombre FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id
           WHERE o.gestion_id = ? ORDER BY a.sigla, o.paralelo""", [gestion_id])
    for f in filas:
        f["docentes"] = docentes(f["id"])
    return filas


def obtener(oid: int) -> dict | None:
    filas = get_db().q("""SELECT o.*, a.sigla, a.nombre FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id
                          WHERE o.id = ?""", [oid])
    return filas[0] if filas else None


def docentes(oid: int) -> list[dict]:
    return get_db().q("""SELECT d.*, u.nombres, u.apellidos FROM oferta_docente d JOIN usuario u ON u.id = d.usuario_id
                         WHERE d.oferta_id = ? ORDER BY d.rol = 'auxiliar', u.apellidos""", [oid])


def _entero(v):
    v = str(v or "").strip()
    return int(v) if v.isdigit() else (None if not v else False)


def agregar(gestion_id: int, sigla: str, paralelo: str, inscritos, uid: int) -> tuple[int | None, list[str]]:
    errores = []
    sigla = (sigla or "").strip().upper().split(" ")[0]
    fila = get_db().q("SELECT * FROM asignatura WHERE sigla = ?", [sigla])
    if not fila:
        errores.append("Elija una asignatura del catálogo.")
    elif not fila[0]["de_la_carrera"]:
        errores.append(f"{sigla} la dicta otra unidad: no se oferta desde la Carrera.")
    paralelo = (paralelo or "A").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,3}", paralelo):
        errores.append("El paralelo es una letra o un código corto (A, B, 1…).")
    n = _entero(inscritos)
    if n is False:
        errores.append("Los inscritos son un número entero.")
    if not errores and get_db().q("SELECT 1 FROM oferta WHERE gestion_id = ? AND asignatura_id = ? AND paralelo = ?",
                                  [gestion_id, fila[0]["id"], paralelo]):
        errores.append(f"{sigla} paralelo {paralelo} ya está en la oferta de esta gestión.")
    if errores:
        return None, errores
    oid = get_db().t.oferta.insert(gestion_id=gestion_id, asignatura_id=fila[0]["id"], paralelo=paralelo,
                                   inscritos=n, creado_por=uid)["id"]
    return oid, []


def quitar(oid: int):
    get_db().execute("DELETE FROM oferta WHERE id = ?", [oid])


def es_titular(usuario_id: int, gestion: dict) -> bool:
    """¿Docente titular (de planta) de la Carrera al inicio de la gestión?"""
    v = vinculos.vigente(usuario_id, gestion["fecha_inicio"])
    return bool(v and v["categoria"] == "titular")


def puede_dictar(usuario_id: int, gestion: dict, rol: str) -> str | None:
    """Error si la persona no puede ser titular de un curso de temporada (None si puede)."""
    if gestion["tipo"] in TEMPORADA and rol == "titular" and not es_titular(usuario_id, gestion):
        return ("Los cursos de verano e invierno solo los dictan docentes titulares de la Carrera "
                "(según su vínculo al inicio de la gestión).")
    return None


def asignar(oid: int, usuario_id: int, rol: str) -> list[str]:
    errores = []
    if rol not in ROLES:
        errores.append("Rol no válido.")
    if not get_db().q("SELECT 1 FROM usuario WHERE id = ?", [usuario_id]):
        errores.append("Elija una persona.")
    elif get_db().q("SELECT 1 FROM oferta_docente WHERE oferta_id = ? AND usuario_id = ?", [oid, usuario_id]):
        errores.append("Esa persona ya está asignada a este paralelo.")
    if not errores:
        gestion = get_db().q("""SELECT g.* FROM oferta o JOIN gestion_academica g ON g.id = o.gestion_id
                                WHERE o.id = ?""", [oid])[0]
        if (e := puede_dictar(usuario_id, gestion, rol)):
            errores.append(e)
    if errores:
        return errores
    get_db().t.oferta_docente.insert(oferta_id=oid, usuario_id=usuario_id, rol=rol)
    return []


def quitar_docente(did: int) -> dict | None:
    filas = get_db().q("SELECT * FROM oferta_docente WHERE id = ?", [did])
    if filas:
        get_db().execute("DELETE FROM oferta_docente WHERE id = ?", [did])
    return filas[0] if filas else None


def sin_vinculo_con_la_carrera(usuario_id: int, gestion: dict) -> bool:
    """¿La persona no tiene vínculo con la Carrera que cubra el inicio de la gestión?"""
    return vinculos.vigente(usuario_id, gestion["fecha_inicio"]) is None


def docentes_posibles(gestion: dict) -> list[dict]:
    """Personas activas; primero las vinculadas a la Carrera al inicio de la gestión."""
    personas = get_db().q("SELECT id, nombres, apellidos FROM usuario WHERE activo = 1 ORDER BY apellidos, nombres")
    for p in personas:
        p["con_vinculo"] = not sin_vinculo_con_la_carrera(p["id"], gestion)
    return sorted(personas, key=lambda p: not p["con_vinculo"])


def materias_de(usuario_id: int, gestion_id: int, solo_titular: bool = True) -> list[dict]:
    """Paralelos que la persona dicta en la gestión (por omisión, como titular)."""
    return get_db().q(
        f"""SELECT o.id, a.sigla, a.nombre, o.paralelo, d.rol FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
            JOIN asignatura a ON a.id = o.asignatura_id WHERE d.usuario_id = ? AND o.gestion_id = ?
            {"AND d.rol = 'titular'" if solo_titular else ""} ORDER BY a.sigla, o.paralelo""", [usuario_id, gestion_id])


def horas_de_docencia(usuario_id: int, gestion_id: int) -> int:
    """Carga de docencia (h/mes) en la gestión: 32 por materia como titular; 0 en verano e invierno."""
    g = get_db().q("SELECT tipo FROM gestion_academica WHERE id = ?", [gestion_id])
    if not g or g[0]["tipo"] in TEMPORADA:
        return 0
    return HORAS_POR_MATERIA * len(materias_de(usuario_id, gestion_id))


# --- Acciones masivas ---------------------------------------------------------------------------------

def mismo_semestre_anio_anterior(gestion: dict) -> dict | None:
    filas = get_db().q("SELECT * FROM gestion_academica WHERE anio = ? AND tipo = ?", [gestion["anio"] - 1, gestion["tipo"]])
    return filas[0] if filas else None


def copiar(origen: dict, destino: dict, con_docentes: bool, uid: int) -> dict:
    """Copia a `destino` los paralelos de `origen` que aún no están (sin inscritos) y, si se pide, sus
    docentes (con las mismas reglas que al asignar a mano). → {paralelos, docentes, avisos}."""
    ya = {(f["asignatura_id"], f["paralelo"]): f["id"] for f in get_db().q(
        "SELECT id, asignatura_id, paralelo FROM oferta WHERE gestion_id = ?", [destino["id"]])}
    res = {"paralelos": 0, "docentes": 0, "avisos": []}
    for o in listar(origen["id"]):
        clave = (o["asignatura_id"], o["paralelo"])
        if clave in ya:
            oid = ya[clave]
        else:
            oid = get_db().t.oferta.insert(gestion_id=destino["id"], asignatura_id=o["asignatura_id"],
                                           paralelo=o["paralelo"], creado_por=uid)["id"]
            res["paralelos"] += 1
        if not con_docentes:
            continue
        for d in o["docentes"]:
            errores = asignar(oid, d["usuario_id"], d["rol"])
            if not errores:
                res["docentes"] += 1
            elif "ya está asignada" not in errores[0]:
                res["avisos"].append(f"{o['sigla']} {o['paralelo']}, {d['nombres']} {d['apellidos']}: {errores[0]}")
    return res


def titular_de(oid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM oferta_docente WHERE oferta_id = ? AND rol = 'titular' ORDER BY id", [oid])
    return filas[0] if filas else None


def fijar_titular(oid: int, usuario_id: int | None) -> list[str]:
    """Deja a `usuario_id` como único titular del paralelo (None: sin titular). Los auxiliares no cambian."""
    actual = titular_de(oid)
    if actual and actual["usuario_id"] == usuario_id:
        return []
    if usuario_id:
        gestion = get_db().q("""SELECT g.* FROM oferta o JOIN gestion_academica g ON g.id = o.gestion_id
                                WHERE o.id = ?""", [oid])[0]
        if (e := puede_dictar(usuario_id, gestion, "titular")):
            return [e]
    get_db().execute("DELETE FROM oferta_docente WHERE oferta_id = ? AND rol = 'titular'", [oid])
    if usuario_id:
        get_db().execute("DELETE FROM oferta_docente WHERE oferta_id = ? AND usuario_id = ?", [oid, usuario_id])
        get_db().t.oferta_docente.insert(oferta_id=oid, usuario_id=usuario_id, rol="titular")
    return []
