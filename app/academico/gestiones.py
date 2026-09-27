"""Gestiones académicas (PLAN.md, sección 24): I, INV, II y VER de cada año.

Se guardan año, tipo y fechas; el código («I-2026», «VER-2026») solo se muestra y el orden sale de
las fechas. El curso de verano se cuenta con la gestión anterior: VER-2026 se dicta en enero de 2027.
"""
from datetime import date

from app.comun.db import get_db

TIPOS = {"I": "Primer semestre", "INV": "Curso de invierno", "II": "Segundo semestre", "VER": "Curso de verano"}


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
    """Crea las cuatro gestiones del año que falten, con las fechas por omisión."""
    if not 2000 <= anio <= 2100:
        raise ValueError("Año fuera de rango.")
    for tipo in TIPOS:
        ini, fin = fechas_por_omision(anio, tipo)
        get_db().execute("""INSERT INTO gestion_academica (anio, tipo, fecha_inicio, fecha_fin) VALUES (?, ?, ?, ?)
                            ON CONFLICT (anio, tipo) DO NOTHING""", [anio, tipo, ini, fin])
    return get_db().q("SELECT * FROM gestion_academica WHERE anio = ? ORDER BY fecha_inicio", [anio])


def actualizar_fechas(gid: int, inicio: str, fin: str) -> str | None:
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
