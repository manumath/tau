"""Unidades de la universidad: UMSA › FCPN › CMAT › IIMAT (PLAN.md, sección 23).

Se usan para el vínculo de cada persona (con la Carrera, el Instituto o ambos), el alcance de los
roles y los informes. La jerarquía se carga en la migración 0022.
"""
from functools import cache

from app.comun.db import get_db

INSTITUTO = "IIMAT"
CARRERA = "CMAT"
# Unidades con las que una persona puede tener vínculo (categoría y jornada).
CON_VINCULO = (INSTITUTO, CARRERA)


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


def instituto() -> int:
    """La unidad cuyo vínculo cuenta para los informes de investigación."""
    return id_de(INSTITUTO)


def con_vinculo() -> list[dict]:
    return [obtener(id_de(s)) for s in CON_VINCULO]


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
