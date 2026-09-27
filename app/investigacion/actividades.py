"""Actividades de investigación (seminarios, congresos, visitas…) y sus participantes."""
from datetime import date

from app.investigacion import adjuntos
from app.comun import personas
from app.comun.db import AHORA, get_db, sin_tildes, transaccion

MODALIDADES = {"presencial": "Presencial", "virtual": "Virtual", "hibrida": "Híbrida"}
AMBITOS = {"local": "Local", "nacional": "Nacional", "internacional": "Internacional"}
ROLES = {"expositor": "Expositor(a)", "organizador": "Organizador(a)", "asistente": "Asistente",
         "comite": "Comité"}


def tipos() -> list[dict]:
    return get_db().q("SELECT * FROM tipo_actividad WHERE activo = 1 ORDER BY orden, nombre")


def obtener(aid: int) -> dict | None:
    filas = get_db().q(
        """SELECT a.*, t.nombre AS tipo FROM actividad a JOIN tipo_actividad t ON t.id = a.tipo_id
           WHERE a.id = ?""", [aid])
    return filas[0] if filas else None


def participantes(aid: int) -> list[dict]:
    filas = get_db().q("SELECT * FROM actividad_participante WHERE actividad_id = ? ORDER BY orden",
                       [aid])
    res = []
    for f in filas:
        p = personas.por_ref(personas.ref(f["investigador_id"], f["externo_id"]))
        if p:
            res.append({**p, "rol": f["rol"]})
    return res


def validar(d: dict, participantes_: list[tuple[str, str]]) -> list[str]:
    errores = []
    if not d["titulo"]:
        errores.append("El título es obligatorio.")
    if not get_db().q("SELECT 1 FROM tipo_actividad WHERE id = ? AND activo = 1", [d["tipo_id"]]):
        errores.append("Seleccione un tipo de actividad.")
    try:
        inicio = date.fromisoformat(d["fecha_inicio"])
        if d["fecha_fin"] and date.fromisoformat(d["fecha_fin"]) < inicio:
            errores.append("La fecha de término no puede ser anterior a la de inicio.")
    except (TypeError, ValueError):
        errores.append("Indique una fecha de inicio válida.")
    if d["modalidad"] not in MODALIDADES:
        errores.append("Modalidad no válida.")
    if d["ambito"] not in AMBITOS:
        errores.append("Ámbito no válido.")
    if not participantes_:
        errores.append("Agregue al menos un participante.")
    if any(rol not in ROLES or not personas.parsear_ref(r) for r, rol in participantes_):
        errores.append("Hay participantes o roles no válidos.")
    if len({r for r, _ in participantes_}) != len(participantes_):
        errores.append("Hay participantes repetidos.")
    return errores


def guardar(d: dict, participantes_: list[tuple[str, str]], usuario_id: int, aid: int | None = None):
    """Crea (aid=None) o actualiza una actividad y reemplaza su lista de participantes."""
    db = get_db()
    with transaccion():  # transacción: o se guarda todo o nada
        if aid is None:
            aid = db.t.actividad.insert(**d, creado_por=usuario_id)["id"]
        else:
            db.t.actividad.update(id=aid, **d)
            db.execute(f"UPDATE actividad SET actualizado_en = {AHORA} WHERE id = ?", [aid])
            db.execute("DELETE FROM actividad_participante WHERE actividad_id = ?", [aid])
        for orden, (r, rol) in enumerate(participantes_):
            db.t.actividad_participante.insert(actividad_id=aid, orden=orden, rol=rol,
                                               **personas.columnas(r))
    return aid


def eliminar(aid: int):
    db = get_db()
    adjuntos.eliminar_de("actividad", aid)
    with transaccion():
        db.execute("DELETE FROM adjunto WHERE entidad = 'actividad' AND entidad_id = ?", [aid])
        db.execute("DELETE FROM actividad WHERE id = ?", [aid])


# --- Permisos -------------------------------------------------------------------

def es_participante(aid: int, uid: int) -> bool:
    return bool(get_db().q("SELECT 1 FROM actividad_participante WHERE actividad_id = ? "
                           "AND investigador_id = ?", [aid, uid]))


def puede_editar(a: dict, uid: int) -> bool:
    return a["creado_por"] == uid or es_participante(a["id"], uid)


def puede_eliminar(a: dict, uid: int) -> bool:
    return a["creado_por"] == uid


# --- Listados --------------------------------------------------------------------

def de_investigador(uid: int, texto: str = "", anio: str = "", tipo_id: str = "") -> list[dict]:
    """Actividades en que participa o que registró, con su rol, más recientes primero."""
    filtros, params = [], {"u": uid}
    if texto.strip():
        filtros.append("(sin_tildes(a.titulo) LIKE :t OR sin_tildes(a.lugar) LIKE :t "
                       "OR sin_tildes(a.institucion) LIKE :t)")
        params["t"] = f"%{sin_tildes(texto.strip())}%"
    if anio.isdigit():
        filtros.append("substr(a.fecha_inicio, 1, 4) = :a")
        params["a"] = anio
    if tipo_id.isdigit():
        filtros.append("a.tipo_id = :tp")
        params["tp"] = int(tipo_id)
    where = "".join(f" AND {f}" for f in filtros)
    return get_db().q(
        f"""SELECT a.*, t.nombre AS tipo,
                   (SELECT rol FROM actividad_participante
                     WHERE actividad_id = a.id AND investigador_id = :u) AS mi_rol,
                   (SELECT COUNT(*) FROM actividad_participante WHERE actividad_id = a.id) AS n_part
            FROM actividad a JOIN tipo_actividad t ON t.id = a.tipo_id
            WHERE (a.creado_por = :u OR EXISTS (SELECT 1 FROM actividad_participante
                     WHERE actividad_id = a.id AND investigador_id = :u)){where}
            ORDER BY a.fecha_inicio DESC, a.id DESC""", params)


def anios_de(uid: int) -> list[str]:
    return [r["a"] for r in get_db().q(
        """SELECT DISTINCT substr(a.fecha_inicio, 1, 4) AS a FROM actividad a
           WHERE a.creado_por = :u OR EXISTS (SELECT 1 FROM actividad_participante
                 WHERE actividad_id = a.id AND investigador_id = :u) ORDER BY a DESC""", {"u": uid})]


def para_selector(uid: int) -> list[dict]:
    """Actividades del investigador para vincular una presentación (las últimas 50)."""
    return de_investigador(uid)[:50]


def fechas_texto(a: dict) -> str:
    """'2026-03-02' / '2026-03-02'…'2026-03-06' → '2 mar 2026' / '2–6 mar 2026'."""
    meses = "ene feb mar abr may jun jul ago sep oct nov dic".split()
    i = date.fromisoformat(a["fecha_inicio"])
    f = date.fromisoformat(a["fecha_fin"]) if a.get("fecha_fin") else i
    if f == i:
        return f"{i.day} {meses[i.month - 1]} {i.year}"
    if (i.year, i.month) == (f.year, f.month):
        return f"{i.day}–{f.day} {meses[i.month - 1]} {i.year}"
    if i.year == f.year:
        return f"{i.day} {meses[i.month - 1]} – {f.day} {meses[f.month - 1]} {i.year}"
    return f"{i.day} {meses[i.month - 1]} {i.year} – {f.day} {meses[f.month - 1]} {f.year}"
