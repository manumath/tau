"""Unidades de la universidad: universidad › facultad › carrera › instituto (PLAN.md, sección 23).

Se usan para el vínculo de cada persona (con la Carrera), el alcance de los roles y los informes. La jerarquía se carga
en la migración 0022 con las unidades de la Carrera de Matemática. Una instalación es de **una carrera**, con su
instituto como unidad opcional dentro (PLAN §73): el código busca cada unidad por su **tipo** (`carrera()`,
`instituto()`, `universidad()`) y nunca por una sigla fija; otra unidad pone sus siglas y nombres con `configurar`
(`scripts/unidades.py`).
"""
from functools import cache

from app.comun.db import get_db

TIPOS = {"universidad": "Universidad", "facultad": "Facultad", "carrera": "Carrera", "instituto": "Instituto"}


def todas() -> list[dict]:
    return get_db().q("SELECT * FROM unidad ORDER BY id")


def obtener(uid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM unidad WHERE id = ?", [uid])
    return filas[0] if filas else None


@cache
def _por_sigla(ruta_db: str, sigla: str) -> int | None:
    filas = get_db().q("SELECT id FROM unidad WHERE sigla = ?", [sigla])
    return filas[0]["id"] if filas else None


def id_de(sigla: str) -> int:
    """Id de la unidad con esa sigla (se guarda en caché por base de datos)."""
    from app.comun.db import dir_datos
    uid = _por_sigla(str(dir_datos()), sigla)
    if uid is None:
        raise ValueError(f"Unidad desconocida: {sigla}")
    return uid


@cache
def _por_tipo(ruta_db: str, tipo: str) -> int | None:
    filas = get_db().q("SELECT id FROM unidad WHERE tipo = ? ORDER BY id LIMIT 1", [tipo])
    return filas[0]["id"] if filas else None


def de_tipo(tipo: str) -> int:
    """Id de la unidad de ese tipo en esta instalación (hay una de cada uno; se guarda en caché por base de datos)."""
    from app.comun.db import dir_datos
    uid = _por_tipo(str(dir_datos()), tipo)
    if uid is None:
        raise ValueError(f"No hay una unidad de tipo «{tipo}».")
    return uid


def de_tipos(tipos) -> list[dict]:
    """Las unidades de esos tipos, en el orden de la jerarquía (para elegir dónde se asigna un rol)."""
    return [u for u in todas() if u["tipo"] in tipos]


def carrera() -> int:
    """La Carrera: la unidad del vínculo de cada persona y la que instala el sistema."""
    return de_tipo("carrera")


def instituto() -> int:
    """El instituto de la Carrera: la unidad cuyo vínculo cuenta para los informes de investigación."""
    return de_tipo("instituto")


def universidad() -> int:
    """La universidad: la unidad de los roles que cubren todas (Administración del sistema, Comisión de calidad)."""
    return de_tipo("universidad")


_nombres: dict[str, dict] = {}   # base de datos → {tipo: unidad}; se vacía al configurar


def _de_la_base() -> dict:
    from app.comun.db import dir_datos
    base = str(dir_datos())
    if base not in _nombres:
        _nombres[base] = {u["tipo"]: u for u in reversed(todas())}   # si hubiera dos de un tipo, la primera
    return _nombres[base]


def nombre_de(tipo: str) -> str:
    """Nombre de la unidad de ese tipo (para membretes y textos: `config.NOMBRE_CARRERA` y compañía)."""
    return _de_la_base()[tipo]["nombre"]


def filiaciones() -> list[str]:
    """Sigla y nombre de cada unidad, del instituto hacia arriba: lo que cuenta como filiación en una publicación."""
    por_tipo = _de_la_base()
    return [x for tipo in ("instituto", "carrera", "facultad", "universidad") if tipo in por_tipo
            for x in (por_tipo[tipo]["sigla"], por_tipo[tipo]["nombre"])]


def filiacion_corta() -> str:
    """Cómo se nombra la filiación en los textos: la sigla del instituto y la de la universidad («IIMAT/UMSA»)."""
    por_tipo = _de_la_base()
    return "/".join(por_tipo[t]["sigla"] for t in ("instituto", "universidad") if t in por_tipo)


def filiacion_larga() -> str:
    """Todas las siglas que cuentan como filiación: «IIMAT, CMAT, FCPN o UMSA»."""
    por_tipo = _de_la_base()
    siglas = [por_tipo[t]["sigla"] for t in ("instituto", "carrera", "facultad", "universidad") if t in por_tipo]
    return siglas[0] if len(siglas) == 1 else ", ".join(siglas[:-1]) + " o " + siglas[-1]


def configurar(tipo: str, sigla: str, nombre: str) -> list[str]:
    """Pone la sigla y el nombre de la unidad de ese tipo (otra carrera que instala el sistema). → errores."""
    sigla, nombre = (sigla or "").strip(), (nombre or "").strip()
    if tipo not in TIPOS:
        return [f"Tipo de unidad desconocido: {tipo} (use {', '.join(TIPOS)})."]
    if not sigla or not nombre:
        return ["Indique la sigla y el nombre."]
    uid = de_tipo(tipo)
    if get_db().q("SELECT 1 FROM unidad WHERE sigla = ? AND id <> ?", [sigla, uid]):
        return [f"La sigla «{sigla}» ya es de otra unidad."]
    get_db().execute("UPDATE unidad SET sigla = ?, nombre = ? WHERE id = ?", [sigla, nombre, uid])
    _por_sigla.cache_clear()
    _nombres.clear()
    return []


def superiores(unidad_id: int) -> list[dict]:
    """La unidad y las que la contienen, de la más específica a la más general."""
    res, actual = [], obtener(unidad_id)
    while actual:
        res.append(actual)
        actual = obtener(actual["superior_id"]) if actual["superior_id"] else None
    return res


def contenidas(unidad_id: int) -> list[int]:
    """Ids de la unidad y de todas las que contiene."""
    ids, pendientes = [], [unidad_id]
    while pendientes:
        u = pendientes.pop()
        ids.append(u)
        pendientes += [f["id"] for f in get_db().q("SELECT id FROM unidad WHERE superior_id = ?", [u])]
    return ids


def texto(unidad_id: int) -> str:
    u = obtener(unidad_id)
    return f"{u['nombre']} ({u['sigla']})" if u else "—"
