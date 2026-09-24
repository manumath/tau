"""Productos de investigación (artículos, libros, reportes, presentaciones…) y sus autores.

Regla institucional: un producto cuenta para los informes del instituto si es indexado o
arbitrado y ya fue aceptado o publicado (ver `cuenta_para_informe`).
"""
import re
from datetime import date

from app import adjuntos, personas
from app.db import get_db, sin_tildes

ESTADOS = {"publicado": "Publicado", "aceptado": "Aceptado", "enviado": "Enviado",
           "en_preparacion": "En preparación"}
REVISIONES = {"indexado": "Indexado", "arbitrado": "Arbitrado", "sin_arbitraje": "Sin arbitraje"}
ESTADOS_INFORME = ("aceptado", "publicado")
TIPO_PRESENTACION = "Presentación"


def tipos() -> list[dict]:
    return get_db().q("SELECT * FROM tipo_producto WHERE activo = 1 ORDER BY orden, nombre")


def tipo(tipo_id) -> dict | None:
    filas = get_db().q("SELECT * FROM tipo_producto WHERE id = ?", [tipo_id])
    return filas[0] if filas else None


def indices() -> list[dict]:
    return get_db().q("SELECT * FROM indice WHERE activo = 1 ORDER BY orden, nombre")


# --- Identificadores -----------------------------------------------------------------

def normalizar_doi(valor: str) -> str:
    v = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", valor.strip(), flags=re.I)
    v = re.sub(r"^doi:\s*", "", v, flags=re.I).strip().lower()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", v):
        raise ValueError("El DOI tiene la forma 10.1234/abcd (puede pegar https://doi.org/…).")
    return v


def normalizar_arxiv(valor: str) -> str:
    v = re.sub(r"^(https?://)?(www\.)?arxiv\.org/(abs|pdf)/", "", valor.strip(), flags=re.I)
    v = re.sub(r"^arxiv:\s*", "", v, flags=re.I).removesuffix(".pdf").strip()
    v = re.sub(r"v\d+$", "", v)
    if not (re.fullmatch(r"\d{4}\.\d{4,5}", v) or re.fullmatch(r"[a-z\-]+(\.[A-Z]{2})?/\d{7}", v)):
        raise ValueError("El identificador arXiv tiene la forma 2401.01234 o math/0501001.")
    return v


# --- Lectura -------------------------------------------------------------------------

def obtener(pid: int) -> dict | None:
    filas = get_db().q(
        """SELECT p.*, t.nombre AS tipo, t.admite_revision FROM producto p
           JOIN tipo_producto t ON t.id = p.tipo_id WHERE p.id = ?""", [pid])
    if not filas:
        return None
    p = filas[0]
    p["autores"] = autores(pid)
    p["indices"] = get_db().q(
        """SELECT i.* FROM producto_indice pi JOIN indice i ON i.id = pi.indice_id
           WHERE pi.producto_id = ? ORDER BY i.orden""", [pid])
    return p


def autores(pid: int) -> list[dict]:
    filas = get_db().q("SELECT * FROM producto_autor WHERE producto_id = ? ORDER BY orden", [pid])
    res = []
    for f in filas:
        p = personas.por_ref(personas.ref(f["investigador_id"], f["externo_id"]))
        if p:
            res.append(p)
    return res


def cuenta_para_informe(p: dict) -> bool:
    return p["revision"] in ("indexado", "arbitrado") and p["estado_publicacion"] in ESTADOS_INFORME


def existente(doi: str | None, arxiv_id: str | None, excluir: int | None = None) -> dict | None:
    """Producto ya registrado con el mismo DOI o arXiv (para no duplicar)."""
    for campo, valor in (("doi", doi), ("arxiv_id", arxiv_id)):
        if valor:
            filas = get_db().q(f"SELECT id FROM producto WHERE {campo} = ? AND id IS NOT ?",
                               [valor, excluir])
            if filas:
                return obtener(filas[0]["id"])
    return None


# --- Validación y escritura ----------------------------------------------------------

def preparar(datos: dict, autores_refs: list[str], indices_ids: list[int],
             pid: int | None = None) -> tuple[dict, list[str]]:
    """Normaliza y valida. Devuelve (datos listos para guardar, errores)."""
    d = {k: (v.strip() if isinstance(v, str) else v) or None for k, v in datos.items()}
    errores = []
    t = tipo(d.get("tipo_id")) if str(d.get("tipo_id") or "").isdigit() else None
    if not t or not t["activo"]:
        errores.append("Seleccione un tipo de producto.")
    if not d.get("titulo"):
        errores.append("El título es obligatorio.")
    anio = str(d.get("anio") or "")
    if not anio.isdigit() or not 1900 <= int(anio) <= date.today().year + 1:
        errores.append(f"Indique un año entre 1900 y {date.today().year + 1}.")
    else:
        d["anio"] = int(anio)
    if d.get("estado_publicacion") not in ESTADOS:
        errores.append("Estado de publicación no válido.")

    # Nivel de revisión según el tipo.
    if t and not t["admite_revision"]:
        d["revision"], indices_ids = "sin_arbitraje", []
    elif d.get("revision") not in REVISIONES:
        errores.append("Indique si el producto es indexado, arbitrado o sin arbitraje.")
    if d.get("revision") != "indexado":
        indices_ids = []
    elif not get_db().q(f"""SELECT 1 FROM indice WHERE cuenta_como_indexado = 1 AND id IN
                           ({','.join('?' * len(indices_ids)) or 'NULL'})""", indices_ids):
        errores.append("Un producto indexado debe figurar en al menos un índice reconocido por el "
                       "instituto (los marcados como válidos para «indexado»).")

    for campo, normalizar in (("doi", normalizar_doi), ("arxiv_id", normalizar_arxiv)):
        if d.get(campo):
            try:
                d[campo] = normalizar(d[campo])
            except ValueError as e:
                errores.append(str(e))
    if not errores and (otro := existente(d.get("doi"), d.get("arxiv_id"), excluir=pid)):
        errores.append(f"Ya existe un producto con ese DOI o arXiv: «{otro['titulo']}». "
                       "Si es suyo, súmese como autor en lugar de registrarlo de nuevo.")

    if t and t["nombre"] != TIPO_PRESENTACION:
        d["actividad_id"] = None
    elif d.get("actividad_id"):
        d["actividad_id"] = int(d["actividad_id"]) if str(d["actividad_id"]).isdigit() else None

    if not autores_refs:
        errores.append("Agregue al menos un autor.")
    elif any(not personas.por_ref(r) for r in autores_refs):
        errores.append("Hay autores no válidos.")
    elif len(set(autores_refs)) != len(autores_refs):
        errores.append("Hay autores repetidos.")
    d["tipo_id"] = int(d["tipo_id"]) if t else None
    d["_indices"] = [int(i) for i in indices_ids]
    return d, errores


def guardar(d: dict, autores_refs: list[str], usuario_id: int, pid: int | None = None) -> int:
    db = get_db()
    indices_ids = d.pop("_indices", [])
    with db.conn:
        if pid is None:
            pid = db.t.producto.insert(**d, creado_por=usuario_id)["id"]
        else:
            db.t.producto.update(id=pid, **d)
            db.execute("UPDATE producto SET actualizado_en = datetime('now') WHERE id = ?", [pid])
            db.execute("DELETE FROM producto_autor WHERE producto_id = ?", [pid])
            db.execute("DELETE FROM producto_indice WHERE producto_id = ?", [pid])
        for orden, r in enumerate(autores_refs):
            db.t.producto_autor.insert(producto_id=pid, orden=orden, **personas.columnas(r))
        for i in indices_ids:
            db.t.producto_indice.insert(producto_id=pid, indice_id=i)
    return pid


def sumar_autor(pid: int, uid: int):
    """Agrega al investigador al final de la lista de autores (si no estaba)."""
    if es_autor(pid, uid):
        return
    db = get_db()
    orden = db.q("SELECT COALESCE(MAX(orden), -1) + 1 AS o FROM producto_autor WHERE producto_id = ?",
                 [pid])[0]["o"]
    db.t.producto_autor.insert(producto_id=pid, orden=orden, investigador_id=uid)


def eliminar(pid: int):
    db = get_db()
    adjuntos.eliminar_de("producto", pid)
    with db.conn:
        db.execute("DELETE FROM adjunto WHERE entidad = 'producto' AND entidad_id = ?", [pid])
        db.execute("DELETE FROM producto WHERE id = ?", [pid])


# --- Permisos --------------------------------------------------------------------------

def es_autor(pid: int, uid: int) -> bool:
    return bool(get_db().q("SELECT 1 FROM producto_autor WHERE producto_id = ? AND investigador_id = ?",
                           [pid, uid]))


def puede_editar(p: dict, uid: int) -> bool:
    return p["creado_por"] == uid or es_autor(p["id"], uid)


def puede_eliminar(p: dict, uid: int) -> bool:
    return p["creado_por"] == uid


# --- Listados ---------------------------------------------------------------------------

def de_investigador(uid: int, texto: str = "", anio: str = "", tipo_id: str = "",
                    solo_informe: bool = False) -> list[dict]:
    """Productos de los que es autor o que registró, más recientes primero."""
    filtros, params = [], {"u": uid}
    if texto.strip():
        filtros.append("(sin_tildes(p.titulo) LIKE :t OR sin_tildes(p.medio) LIKE :t)")
        params["t"] = f"%{sin_tildes(texto.strip())}%"
    if anio.isdigit():
        filtros.append("p.anio = :a")
        params["a"] = int(anio)
    if tipo_id.isdigit():
        filtros.append("p.tipo_id = :tp")
        params["tp"] = int(tipo_id)
    if solo_informe:
        filtros.append("p.revision IN ('indexado', 'arbitrado') "
                       "AND p.estado_publicacion IN ('aceptado', 'publicado')")
    where = "".join(f" AND {f}" for f in filtros)
    filas = get_db().q(
        f"""SELECT p.id FROM producto p
            WHERE (p.creado_por = :u OR EXISTS (SELECT 1 FROM producto_autor
                     WHERE producto_id = p.id AND investigador_id = :u)){where}
            ORDER BY p.anio DESC, p.id DESC""", params)
    return [obtener(f["id"]) for f in filas]


def anios_de(uid: int) -> list[int]:
    return [r["anio"] for r in get_db().q(
        """SELECT DISTINCT anio FROM producto p WHERE p.creado_por = :u OR EXISTS
           (SELECT 1 FROM producto_autor WHERE producto_id = p.id AND investigador_id = :u)
           ORDER BY anio DESC""", {"u": uid})]


def cita(p: dict) -> str:
    """Referencia en texto: 'Noether, E.; Turing, A. (2026). Título. Revista, 12(3), 1–20.'"""
    autores_ = "; ".join(personas.nombre_cita(a) for a in p["autores"])
    partes = [f"{autores_} ({p['anio']}). {p['titulo'].rstrip('.')}."]
    medio = p.get("medio") or ""
    if p.get("volumen"):
        medio += f", {p['volumen']}" + (f"({p['numero']})" if p.get("numero") else "")
    if p.get("paginas"):
        medio += f", {p['paginas']}"
    if medio:
        partes.append(medio.lstrip(", ") + ".")
    return " ".join(partes)
