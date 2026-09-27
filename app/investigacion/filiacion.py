"""Filiación del instituto en las publicaciones (IIMAT, CMAT, FCPN o UMSA; vale la doble filiación).

Por cada autor del instituto se registra si firmó con la filiación (1), si no (0) o si aún no se
declaró (None). Los informes institucionales solo cuentan un producto si al menos un autor
vinculado en la fecha firmó con ella.
"""
import re

from app import config
from app.db import get_db, sin_tildes

OPCIONES = {"": "Filiación sin declarar", "1": "Firmó con IIMAT/UMSA", "0": "Sin filiación del instituto"}


def detecta(afiliacion: str | None) -> bool:
    """¿El texto de afiliación (p. ej., de Crossref) menciona al instituto o a la UMSA?"""
    if not afiliacion:
        return False
    texto = sin_tildes(afiliacion).lower()
    for nombre in config.FILIACIONES:
        n = sin_tildes(nombre).lower()
        if " " not in n and len(n) <= 6:  # sigla: como palabra completa
            if re.search(rf"\b{re.escape(n)}\b", texto):
                return True
        elif n in texto:
            return True
    return False


def normalizar(valor) -> int | None:
    v = str(valor if valor is not None else "").strip()
    return int(v) if v in ("0", "1") else None


# Solo se pide declarar la filiación donde importa: productos indexados o arbitrados (los únicos que
# pueden contar para el instituto).
REVISIONES_QUE_CUENTAN = ("indexado", "arbitrado")


def pendientes(uid: int) -> int:
    """Productos indexados o arbitrados en que es autor(a) y no ha declarado su filiación."""
    return get_db().q("""SELECT COUNT(*) n FROM producto_autor pa JOIN producto p ON p.id = pa.producto_id
                         WHERE pa.investigador_id = ? AND pa.filiacion_instituto IS NULL
                           AND p.revision IN ('indexado', 'arbitrado')""", [uid])[0]["n"]


def declarar(uid: int, producto_ids: list[int], valor: int) -> int:
    """El investigador declara su propia filiación en varios productos. → cuántos cambió."""
    if valor not in (0, 1) or not producto_ids:
        return 0
    marcas = ",".join("?" * len(producto_ids))
    antes = get_db().q(f"""SELECT COUNT(*) n FROM producto_autor WHERE investigador_id = ?
                           AND producto_id IN ({marcas}) AND filiacion_instituto IS NOT ?""",
                       [uid, *producto_ids, valor])[0]["n"]
    get_db().execute(f"""UPDATE producto_autor SET filiacion_instituto = ? WHERE investigador_id = ?
                         AND producto_id IN ({marcas})""", [valor, uid, *producto_ids])
    return antes


def estado_producto(p: dict) -> int | None:
    """Filiación de un producto: 1 si algún autor del instituto firmó con ella, 0 si ninguno (y
    todos lo declararon), None si falta declarar."""
    valores = [a.get("filiacion") for a in p["autores"] if a["interno"]]
    if 1 in valores:
        return 1
    return 0 if valores and all(v == 0 for v in valores) else None


def leer_agradece(valores: list[str] | None) -> dict[int, int | None]:
    """Campos «agradece» del formulario ('<proyecto>:1', '<proyecto>:0', '<proyecto>:') → {proyecto: valor}."""
    res = {}
    for v in valores or []:
        pid, _, valor = str(v).partition(":")
        if pid.isdigit():
            res[int(pid)] = normalizar(valor)
    return res
