"""Actividades de investigación (seminarios, congresos, visitas…) y sus participantes."""
from datetime import date

from app.investigacion import adjuntos
from app.comun import personas
from app.comun.db import AHORA, get_db, sin_tildes, transaccion

MODALIDADES = {"presencial": "Presencial", "virtual": "Virtual", "hibrida": "Híbrida"}
AMBITOS = {"local": "Local", "nacional": "Nacional", "internacional": "Internacional"}
ROLES = {"expositor": "Expositor(a)", "organizador": "Organizador(a)", "asistente": "Asistente",
         "comite": "Comité", "distinguido": "Distinguido(a)", "revisor": "Revisor(a)", "responsable": "Responsable"}
# Tipos con datos propios (PLAN §40) y el rol que debe tener al menos un participante.
PREMIO, ARBITRAJE, SERVICIO = "Premio o distinción", "Arbitraje de artículos", "Prestación de servicios"
ROL_DEL_TIPO = {PREMIO: "distinguido", ARBITRAJE: "revisor", SERVICIO: "responsable"}
MONEDAS = {"BOB": "Bolivianos (Bs)", "USD": "Dólares (USD)"}
FINANCIAMIENTOS = {"interno": "Interno (de la universidad)", "externo": "Externo"}
CAMPOS_PROPIOS = ("cantidad", "revista_id", "monto", "moneda", "financiamiento", "ingresos")


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


def nombre_tipo(tipo_id) -> str | None:
    filas = get_db().q("SELECT nombre FROM tipo_actividad WHERE id = ?", [tipo_id])
    return filas[0]["nombre"] if filas else None


def anual(a: dict) -> bool:
    """Una entrada de todo un año (el arbitraje se registra por revista y año)."""
    return bool(a.get("fecha_fin")) and a["fecha_inicio"][4:] == "-01-01" and a["fecha_fin"][4:] == "-12-31" \
        and a["fecha_inicio"][:4] == a["fecha_fin"][:4]


def validar(d: dict, participantes_: list[tuple[str, str]]) -> list[str]:
    errores = []
    tipo = nombre_tipo(d["tipo_id"])
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
    rol = ROL_DEL_TIPO.get(tipo)
    if rol and participantes_ and not any(x == rol for _, x in participantes_):
        errores.append(f"Indique quién es {ROLES[rol].lower()}: al menos un participante con ese rol.")
    if tipo == ARBITRAJE and not (isinstance(d.get("cantidad"), int) and d["cantidad"] > 0):
        errores.append("Indique cuántos artículos arbitró para esa revista en el año.")
    if tipo == ARBITRAJE and not d.get("institucion"):
        errores.append("Indique la revista.")
    if tipo == SERVICIO:
        if d.get("monto") is not None and d.get("moneda") not in MONEDAS:
            errores.append("Indique la moneda del monto.")
        if d.get("financiamiento") not in (None, *FINANCIAMIENTOS):
            errores.append("Origen del financiamiento no válido.")
    return errores


def revista_del_catalogo(titulo: str | None) -> int | None:
    """La revista del catálogo con ese título (sin distinguir mayúsculas), si existe."""
    if not titulo:
        return None
    filas = get_db().q("SELECT id FROM revista WHERE lower(titulo) = lower(?) LIMIT 1", [titulo.strip()])
    return filas[0]["id"] if filas else None


def entero(texto) -> tuple[int | None, bool]:
    """'1 500' / '1500' → (1500, True); '' → (None, True); '15,5' → (None, False)."""
    t = str(texto or "").replace(" ", "").replace("\u00a0", "")
    if not t:
        return None, True
    return (int(t), True) if t.isdigit() else (None, False)


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
    if anual(a):
        return a["fecha_inicio"][:4]
    i = date.fromisoformat(a["fecha_inicio"])
    f = date.fromisoformat(a["fecha_fin"]) if a.get("fecha_fin") else i
    if f == i:
        return f"{i.day} {meses[i.month - 1]} {i.year}"
    if (i.year, i.month) == (f.year, f.month):
        return f"{i.day}–{f.day} {meses[i.month - 1]} {i.year}"
    if i.year == f.year:
        return f"{i.day} {meses[i.month - 1]} – {f.day} {meses[f.month - 1]} {i.year}"
    return f"{i.day} {meses[i.month - 1]} {i.year} – {f.day} {meses[f.month - 1]} {f.year}"
