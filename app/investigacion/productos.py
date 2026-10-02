"""Productos de investigación (artículos, libros, reportes, presentaciones…) y sus autores.

Regla institucional: un producto cuenta para los informes del instituto si es indexado o
arbitrado y ya fue aceptado o publicado (ver `cuenta_para_informe`).
"""
import re
from datetime import date

from app.investigacion import adjuntos, msc, revistas
from app.comun import personas
from app.comun.db import AHORA, DISTINTO_DE, get_db, sin_tildes, transaccion

ESTADOS = {"publicado": "Publicado", "aceptado": "Aceptado", "enviado": "Enviado",
           "en_preparacion": "En preparación"}
REVISIONES = {"indexado": "Indexado", "arbitrado": "Arbitrado", "sin_arbitraje": "Sin arbitraje"}
ESTADOS_INFORME = ("aceptado", "publicado")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
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
    # Revista del catálogo (si la tiene): si está verificada, la revisión y los índices vienen de ella.
    p["revista"] = revistas.obtener(p["revista_id"]) if p.get("revista_id") else None
    p["clasificacion_catalogo"] = bool(p["revista"] and p["revista"]["estado"] == "verificada")
    p["indices"] = get_db().q(
        """SELECT i.* FROM producto_indice pi JOIN indice i ON i.id = pi.indice_id
           WHERE pi.producto_id = ? ORDER BY i.orden""", [pid])
    p["msc"] = msc.de_producto(pid)
    return p


def autores(pid: int) -> list[dict]:
    filas = get_db().q("SELECT * FROM producto_autor WHERE producto_id = ? ORDER BY orden", [pid])
    res = []
    for f in filas:
        p = personas.por_ref(personas.ref(f["investigador_id"], f["externo_id"]))
        if p:
            res.append({**p, "filiacion": f["filiacion_instituto"]})
    return res


def cuenta_para_informe(p: dict) -> bool:
    return p["revision"] in ("indexado", "arbitrado") and p["estado_publicacion"] in ESTADOS_INFORME


def existente(doi: str | None, arxiv_id: str | None, excluir: int | None = None) -> dict | None:
    """Producto ya registrado con el mismo DOI o arXiv (para no duplicar)."""
    for campo, valor in (("doi", doi), ("arxiv_id", arxiv_id)):
        if valor:
            filas = get_db().q(f"SELECT id FROM producto WHERE {campo} = ? AND id {DISTINTO_DE} ?",
                               [valor, excluir])
            if filas:
                return obtener(filas[0]["id"])
    return None


# --- Validación y escritura ----------------------------------------------------------

def preparar(datos: dict, autores_refs: list[str], indices_ids: list[int],
             pid: int | None = None) -> tuple[dict, list[str]]:
    """Normaliza y valida. Devuelve (datos listos para guardar, errores). Si `datos` trae `msc` (la
    clasificación MSC2020, el principal primero), se valida y se guarda; si no, no se toca."""
    datos = dict(datos)
    codigos_msc = datos.pop("msc", None)
    d = {k: (v.strip() if isinstance(v, str) else v) or None for k, v in datos.items()}
    errores = []
    if codigos_msc is not None:
        d["_msc"], errores_msc = msc.validar(codigos_msc)
        errores += errores_msc
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
    if "mes" in d:
        mes = str(d.get("mes") or "")
        if mes and not (mes.isdigit() and 1 <= int(mes) <= 12):
            errores.append("Mes de publicación no válido.")
        else:
            d["mes"] = int(mes) if mes else None
    if d.get("estado_publicacion") not in ESTADOS:
        errores.append("Estado de publicación no válido.")

    # Revista del catálogo: solo en artículos en revista. Si está verificada, fija el nivel de
    # revisión y los índices según el año (no los declara el autor) y el nombre del medio.
    rid = str(d.get("revista_id") or "")
    if not t or t["nombre"] != revistas.TIPO_ARTICULO:
        d["revista_id"] = None
    elif rid:
        r = revistas.obtener(int(rid)) if rid.isdigit() else None
        if not r:
            errores.append("La revista elegida no existe en el catálogo.")
            d["revista_id"] = None
        else:
            d["revista_id"], d["medio"] = r["id"], r["titulo"]
            c = revistas.clasificacion(r["id"], d["anio"]) if isinstance(d.get("anio"), int) else None
            if c:
                d["revision"] = c["revision"]
                indices_ids = [x["indice_id"] for x in c["indices"]] if c["revision"] == "indexado" else []
    else:
        d["revista_id"] = None

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


def guardar(d: dict, autores_refs: list[str], usuario_id: int, pid: int | None = None,
            filiaciones: list | None = None) -> int:
    """`filiaciones`: en el orden de los autores, 1 / 0 / None (sin declarar) para los del
    instituto; se ignora en los externos."""
    from app.investigacion.filiacion import normalizar
    filiaciones = list(filiaciones or [])
    filiaciones += [None] * (len(autores_refs) - len(filiaciones))
    db = get_db()
    indices_ids = d.pop("_indices", [])
    codigos_msc = d.pop("_msc", None)
    with transaccion():
        if pid is None:
            pid = db.t.producto.insert(**d, creado_por=usuario_id)["id"]
        else:
            db.t.producto.update(id=pid, **d)
            db.execute(f"UPDATE producto SET actualizado_en = {AHORA} WHERE id = ?", [pid])
            db.execute("DELETE FROM producto_autor WHERE producto_id = ?", [pid])
            db.execute("DELETE FROM producto_indice WHERE producto_id = ?", [pid])
        for orden, (r, fil) in enumerate(zip(autores_refs, filiaciones)):
            cols = personas.columnas(r)
            db.t.producto_autor.insert(producto_id=pid, orden=orden, **cols,
                                       filiacion_instituto=normalizar(fil) if cols["investigador_id"] else None)
        for i in indices_ids:
            db.t.producto_indice.insert(producto_id=pid, indice_id=i)
        if codigos_msc is not None:
            msc.guardar_de_producto(pid, codigos_msc)
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
    with transaccion():
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
                    solo_informe: bool = False, sin_filiacion: bool = False, area: str = "") -> list[dict]:
    """Productos de los que es autor o que registró, más recientes primero. `sin_filiacion`: solo
    aquellos en que es autor(a) y no ha declarado si firmó con la filiación del instituto. `area`:
    sección MSC ('11'), en su código principal o en uno secundario."""
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
    if re.fullmatch(r"\d{2}", area):
        filtros.append("EXISTS (SELECT 1 FROM producto_msc WHERE producto_id = p.id AND substr(codigo, 1, 2) = :ar)")
        params["ar"] = area
    if solo_informe:
        filtros.append("p.revision IN ('indexado', 'arbitrado') "
                       "AND p.estado_publicacion IN ('aceptado', 'publicado')")
    if sin_filiacion:  # solo donde importa: indexados o arbitrados
        filtros.append("p.revision IN ('indexado', 'arbitrado') AND EXISTS (SELECT 1 FROM producto_autor "
                       "WHERE producto_id = p.id AND investigador_id = :u AND filiacion_instituto IS NULL)")
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


def areas_de(uid: int) -> list[dict]:
    """Secciones MSC de los productos de la persona (para el filtro de su lista)."""
    return get_db().q(
        """SELECT DISTINCT s.* FROM producto p JOIN producto_msc pm ON pm.producto_id = p.id
           JOIN msc s ON s.codigo = substr(pm.codigo, 1, 2) || '-XX'
           WHERE p.creado_por = :u OR EXISTS
           (SELECT 1 FROM producto_autor WHERE producto_id = p.id AND investigador_id = :u)
           ORDER BY s.codigo""", {"u": uid})
