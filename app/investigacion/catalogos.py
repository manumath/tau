"""Catálogos administrables desde la interfaz (PLAN.md §47): tipos de actividad, tipos de producto e
índices. Los del sistema (`del_sistema = 1`, los que traen las migraciones) los reconocen por su nombre el
anexo, la Guía de Antecedentes, el CV y las importaciones: solo se reordenan y se activan o desactivan (en
los índices, además, se cambia si cuentan como indexado o arbitrado). Los agregados desde la interfaz se
renombran y, si nadie los usó, se eliminan. Un tipo nuevo cuenta de forma genérica: en formularios, listas,
CV y memoria, pero no en las categorías del anexo ni de la Guía."""
from app.comun.db import get_db, sin_tildes, transaccion

LARGO_NOMBRE = 80
# Por catálogo: tabla, títulos, opciones propias (columna → texto) y consulta de uso.
CATALOGOS = {
    "actividades": {"tabla": "tipo_actividad", "titulo": "Tipos de actividad", "singular": "tipo de actividad",
                    "opciones": {},
                    "uso": "SELECT count(*) AS n FROM actividad WHERE tipo_id = ?"},
    "productos": {"tabla": "tipo_producto", "titulo": "Tipos de producto", "singular": "tipo de producto",
                  "opciones": {"admite_revision": "Puede ser indexado o arbitrado (si no, siempre «sin arbitraje»)"},
                  "uso": "SELECT count(*) AS n FROM producto WHERE tipo_id = ?"},
    "indices": {"tabla": "indice", "titulo": "Índices", "singular": "índice",
                "opciones": {"cuenta_como_indexado": "Cuenta como «indexado» (un producto en él es indexado)",
                             "cuenta_como_arbitrado": "Cuenta como «arbitrado» (sus revistas son arbitradas)"},
                "uso": """SELECT (SELECT count(*) FROM producto_indice WHERE indice_id = ?)
                                 + (SELECT count(*) FROM revista_indice WHERE indice_id = ?) AS n"""},
}
# Opciones que cambian la clasificación de lo ya registrado (se advierte y se audita).
POLITICA = ("cuenta_como_indexado", "cuenta_como_arbitrado")


def _c(catalogo: str) -> dict:
    return CATALOGOS[catalogo]


def uso(catalogo: str, xid: int) -> int:
    c = _c(catalogo)
    return get_db().q(c["uso"], [xid] * c["uso"].count("?"))[0]["n"]


def listar(catalogo: str) -> list[dict]:
    filas = get_db().q(f"SELECT * FROM {_c(catalogo)['tabla']} ORDER BY orden, nombre")
    for f in filas:
        f["uso"] = uso(catalogo, f["id"])
    return filas


def obtener(catalogo: str, xid: int) -> dict | None:
    filas = get_db().q(f"SELECT * FROM {_c(catalogo)['tabla']} WHERE id = ?", [xid])
    return filas[0] if filas else None


def validar(catalogo: str, datos: dict, xid: int | None = None) -> tuple[dict, list[str]]:
    """→ (datos limpios, errores). En uno del sistema, el nombre no cambia."""
    c, actual = _c(catalogo), obtener(catalogo, xid) if xid else None
    d = {k: (1 if datos.get(k) else 0) for k in c["opciones"]}
    errores = []
    if actual and actual["del_sistema"]:
        d["nombre"] = actual["nombre"]
    else:
        d["nombre"] = " ".join((datos.get("nombre") or "").split())
        if not d["nombre"]:
            errores.append("El nombre es obligatorio.")
        elif len(d["nombre"]) > LARGO_NOMBRE:
            errores.append(f"El nombre admite hasta {LARGO_NOMBRE} caracteres.")
        elif any(sin_tildes(f["nombre"]).lower() == sin_tildes(d["nombre"]).lower() and f["id"] != xid
                 for f in get_db().q(f"SELECT id, nombre FROM {c['tabla']}")):
            errores.append(f"Ya existe un {c['singular']} con ese nombre.")
    return d, errores


def crear(catalogo: str, d: dict) -> int:
    tabla = _c(catalogo)["tabla"]
    orden = get_db().q(f"SELECT COALESCE(MAX(orden), 0) + 10 AS o FROM {tabla}")[0]["o"]
    return get_db().t[tabla].insert(**d, orden=orden, activo=1, del_sistema=0)["id"]


def actualizar(catalogo: str, xid: int, d: dict):
    get_db().t[_c(catalogo)["tabla"]].update(id=xid, **d)


def activar(catalogo: str, xid: int, activo: bool):
    get_db().execute(f"UPDATE {_c(catalogo)['tabla']} SET activo = ? WHERE id = ?", [int(activo), xid])


def mover(catalogo: str, xid: int, delta: int):
    """Sube (-1) o baja (+1) en el orden en que se ofrece en los formularios."""
    tabla = _c(catalogo)["tabla"]
    ids = [x["id"] for x in get_db().q(f"SELECT id FROM {tabla} ORDER BY orden, nombre")]
    if xid not in ids:
        return
    i = ids.index(xid)
    if 0 <= i + delta < len(ids):
        ids[i], ids[i + delta] = ids[i + delta], ids[i]
    with transaccion():
        for n, x in enumerate(ids, start=1):
            get_db().execute(f"UPDATE {tabla} SET orden = ? WHERE id = ?", [n * 10, x])


def reclasificar_indice(iid: int) -> int:
    """Tras cambiar la política de un índice: aplica el catálogo a los artículos de las revistas verificadas que
    figuran en él (los de revistas sin verificar conservan lo declarado por sus autores). → artículos que cambiaron."""
    from app.investigacion import revistas
    return sum(revistas.reclasificar(f["revista_id"]) for f in get_db().q(
        "SELECT DISTINCT revista_id FROM revista_indice WHERE indice_id = ?", [iid]))


def eliminar(catalogo: str, xid: int) -> str | None:
    """Solo uno agregado desde la interfaz que nadie haya usado. → error o None."""
    x = obtener(catalogo, xid)
    if not x:
        return "No existe."
    if x["del_sistema"]:
        return "Es del sistema: no se elimina (puede desactivarlo)."
    if uso(catalogo, xid):
        return "Está en uso: no se elimina (puede desactivarlo)."
    get_db().execute(f"DELETE FROM {_c(catalogo)['tabla']} WHERE id = ?", [xid])
    return None
