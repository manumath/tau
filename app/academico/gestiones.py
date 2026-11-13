"""Gestiones académicas (PLAN.md, sección 24): I, INV, II y VER de cada año.

Se guardan año, tipo y fechas; el código («I-2026», «VER-2026») solo se muestra y el orden sale de
las fechas. El curso de verano se cuenta con la gestión anterior: VER-2026 se dicta en enero de 2027.
"""
from datetime import date

from app.comun.db import AHORA, auditar, get_db, transaccion

TIPOS = {"I": "Primer semestre", "INV": "Curso de invierno", "II": "Segundo semestre", "VER": "Curso de verano"}
# Ciclo de vida (PLAN §66): planificación (se edita libremente y se puede borrar) → activa (el semestre está en marcha:
# los cambios piden motivo y fecha) → concluida (historial, solo lectura).
ESTADOS = {"planificacion": "En planificación", "activa": "Activa", "concluida": "Concluida"}
TONOS = {"planificacion": "azul", "activa": "verde", "concluida": "gris"}
ICONOS = {"planificacion": "pencil", "activa": "play", "concluida": "archive"}


def fechas_por_omision(anio: int, tipo: str) -> tuple[str, str]:
    """Fechas propuestas al crear una gestión (la Dirección las ajusta al calendario aprobado)."""
    return {"I": (f"{anio}-02-01", f"{anio}-06-30"), "INV": (f"{anio}-07-01", f"{anio}-07-31"),
            "II": (f"{anio}-08-01", f"{anio}-12-31"), "VER": (f"{anio + 1}-01-02", f"{anio + 1}-01-31")}[tipo]


def codigo(g: dict) -> str:
    return f"{g['tipo']}-{g['anio']}"


def nombre(g: dict) -> str:
    extra = f" (enero de {g['anio'] + 1})" if g["tipo"] == "VER" else ""
    return f"{TIPOS[g['tipo']]} {g['anio']}{extra}"


def listar() -> list[dict]:
    return get_db().q("SELECT * FROM gestion_academica ORDER BY fecha_inicio DESC")


def obtener(gid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM gestion_academica WHERE id = ?", [gid])
    return filas[0] if filas else None


def por_codigo(texto: str) -> dict | None:
    """«I-2026», «ver-2026» → la gestión (None si el texto no es un código o no existe)."""
    tipo, _, anio = (texto or "").strip().upper().rpartition("-")
    if tipo not in TIPOS or not anio.isdigit():
        return None
    filas = get_db().q("SELECT * FROM gestion_academica WHERE anio = ? AND tipo = ?", [int(anio), tipo])
    return filas[0] if filas else None


def crear_anio(anio: int) -> list[dict]:
    """Crea las cuatro gestiones del año que falten, con las fechas por omisión (sin oferta; la
    oferta inicial de los semestres la agrega app.academico.oferta.ofertar_troncales)."""
    return [g for g, _ in crear_anio_con_nuevas(anio)]


def crear_anio_con_nuevas(anio: int) -> list[tuple[dict, bool]]:
    """Como crear_anio, pero indica cuáles gestiones se crearon ahora: [(gestión, nueva)]."""
    if not 2000 <= anio <= 2100:
        raise ValueError("Año fuera de rango.")
    antes = {f["tipo"] for f in get_db().q("SELECT tipo FROM gestion_academica WHERE anio = ?", [anio])}
    for tipo in TIPOS:
        ini, fin = fechas_por_omision(anio, tipo)
        get_db().execute("""INSERT INTO gestion_academica (anio, tipo, fecha_inicio, fecha_fin) VALUES (?, ?, ?, ?)
                            ON CONFLICT (anio, tipo) DO NOTHING""", [anio, tipo, ini, fin])
    return [(g, g["tipo"] not in antes)
            for g in get_db().q("SELECT * FROM gestion_academica WHERE anio = ? ORDER BY fecha_inicio", [anio])]


def edicion_libre(g: dict) -> bool:
    """¿Se edita la oferta y los docentes sin motivo ni fecha de efecto? Solo en planificación. Con la gestión activa, los
    cambios pasan por `app.academico.cambios` (con motivo y registro); la concluida es historial (PLAN §66)."""
    return g["estado"] == "planificacion"


def crear(anio: int, tipo: str, uid: int, concluida: bool = False) -> tuple[dict | None, str | None]:
    """Crea una gestión suelta, con las fechas por omisión. `concluida`: para cargar el historial de un semestre que ya
    terminó (se crea directamente como concluida). → (gestión, error)."""
    if tipo not in TIPOS:
        return None, "Elija el tipo de gestión."
    if not 2000 <= anio <= 2100:
        return None, "Indique un año entre 2000 y 2100."
    if get_db().q("SELECT 1 FROM gestion_academica WHERE anio = ? AND tipo = ?", [anio, tipo]):
        return None, f"Ya existe la gestión {tipo}-{anio}."
    inicio, fin = fechas_por_omision(anio, tipo)
    if concluida and fin >= date.today().isoformat():
        return None, f"{tipo}-{anio} todavía no termina (el {fin}): no puede crearse como concluida."
    with transaccion():
        gid = get_db().t.gestion_academica.insert(anio=anio, tipo=tipo, fecha_inicio=inicio, fecha_fin=fin)["id"]
        if concluida:
            get_db().execute(f"""UPDATE gestion_academica SET estado = 'concluida', activada_en = fecha_inicio,
                                 concluida_en = {AHORA}, concluida_por = ?,
                                 motivo_conclusion = 'Gestión pasada, creada para cargar su historial.' WHERE id = ?""",
                             [uid, gid])
        auditar(uid, "crear_gestion", "gestion_academica", gid, f"{tipo}-{anio}" + (" (historial)" if concluida else ""))
    return obtener(gid), None


def en_uso(gid: int) -> list[str]:
    """Qué otras cosas dependen de la gestión (impiden borrarla)."""
    n = get_db().q("SELECT COUNT(*) n FROM convocatoria_auxiliatura WHERE gestion_id = ?", [gid])[0]["n"]
    return [f"{n} convocatoria{'s' if n != 1 else ''} a auxiliaturas"] if n else []


def eliminar(gid: int, uid: int) -> str | None:
    """Borra una gestión en planificación con su oferta y docentes. → error o None."""
    g = obtener(gid)
    if not g:
        return "La gestión no existe."
    if g["estado"] != "planificacion":
        return "Solo se borra una gestión en planificación: una gestión activa o concluida es parte del historial."
    uso = en_uso(gid)
    if uso:
        return f"No se puede borrar {codigo(g)}: tiene {' y '.join(uso)}."
    paralelos = get_db().q("SELECT COUNT(*) n FROM oferta WHERE gestion_id = ?", [gid])[0]["n"]
    with transaccion():
        get_db().execute("DELETE FROM oferta WHERE gestion_id = ?", [gid])
        get_db().execute("DELETE FROM gestion_academica WHERE id = ?", [gid])
        auditar(uid, "eliminar_gestion", "gestion_academica", gid, f"{codigo(g)} (en planificación, {paralelos} paralelo(s))")
    return None


def actualizar_fechas(gid: int, inicio: str, fin: str) -> str | None:
    g = obtener(gid)
    if g and g["estado"] == "concluida":
        return "Una gestión concluida es parte del historial: sus fechas no cambian."
    try:
        i, f = date.fromisoformat(inicio), date.fromisoformat(fin)
    except ValueError:
        return "Indique fechas válidas."
    if f < i:
        return "El término no puede ser anterior al inicio."
    get_db().execute("UPDATE gestion_academica SET fecha_inicio = ?, fecha_fin = ? WHERE id = ?",
                     [i.isoformat(), f.isoformat(), gid])
    return None


def actual(hoy: str | None = None) -> dict | None:
    """La gestión en curso; si no hay ninguna, la próxima; si tampoco, la más reciente."""
    h = hoy or date.today().isoformat()
    filas = get_db().q("SELECT * FROM gestion_academica WHERE fecha_inicio <= ? AND fecha_fin >= ? "
                       "ORDER BY fecha_inicio DESC LIMIT 1", [h, h]) \
        or get_db().q("SELECT * FROM gestion_academica WHERE fecha_inicio > ? ORDER BY fecha_inicio LIMIT 1", [h]) \
        or get_db().q("SELECT * FROM gestion_academica ORDER BY fecha_inicio DESC LIMIT 1")
    return filas[0] if filas else None
