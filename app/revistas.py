"""Catálogo de revistas con su indexación por año.

- Una revista `verificada` (revisada por la administración) define el nivel de revisión y los
  índices de los artículos publicados en ella, según el año de publicación. Una `pendiente` (la
  propuso un investigador o se creó al importar) todavía no: rige lo que declaró el autor.
- `revista_indice` registra en qué años figura la revista en cada índice, con la fuente
  consultada y un enlace de evidencia (transparencia de los datos; IAC-CINDA, criterio 3.6.3).
"""
import re

from app import config
from app.db import get_db, sin_tildes

ESTADOS = {"pendiente": "Pendiente de verificar", "verificada": "Verificada"}
CUARTILES = ("Q1", "Q2", "Q3", "Q4")


# --- ISSN ----------------------------------------------------------------------------------------

def normalizar_issn(texto: str | None) -> str | None:
    """'2049-3630', '20493630', 'ISSN 2049-3630' → '2049-3630'. ValueError si el dígito
    verificador no coincide; None si viene vacío."""
    if not texto or not str(texto).strip():
        return None
    t = re.sub(r"[^0-9Xx]", "", str(texto).upper().replace("ISSN", ""))
    if len(t) != 8 or not t[:7].isdigit():
        raise ValueError(f"ISSN no válido: {texto}")
    suma = sum(int(d) * (8 - i) for i, d in enumerate(t[:7]))
    control = (11 - suma % 11) % 11
    if t[7] != ("X" if control == 10 else str(control)):
        raise ValueError(f"ISSN no válido (dígito verificador): {texto}")
    return f"{t[:4]}-{t[4:]}"


# --- Consultas -----------------------------------------------------------------------------------

def obtener(rid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM revista WHERE id = ?", [rid])
    return filas[0] if filas else None


def por_issn(issn: str | None) -> dict | None:
    if not issn:
        return None
    filas = get_db().q("SELECT * FROM revista WHERE issn = :i OR eissn = :i", {"i": issn})
    return filas[0] if filas else None


def buscar(texto: str = "", estado: str = "", limite: int = 200) -> list[dict]:
    t = texto.strip()
    patron = f"%{sin_tildes(t)}%"
    return get_db().q(
        """SELECT r.*, (SELECT COUNT(*) FROM producto p WHERE p.revista_id = r.id) AS n_productos
           FROM revista r
           WHERE (:t = '' OR sin_tildes(r.titulo) LIKE :p OR r.issn LIKE :q OR r.eissn LIKE :q)
             AND (:e = '' OR r.estado = :e)
           ORDER BY r.estado = 'verificada', sin_tildes(r.titulo) LIMIT :l""",
        {"t": t, "p": patron, "q": f"%{t}%", "e": estado, "l": limite})


def indexaciones(rid: int) -> list[dict]:
    return get_db().q(
        """SELECT ri.*, i.nombre AS indice, i.cuenta_como_indexado, u.nombres || ' ' || u.apellidos AS verificador
           FROM revista_indice ri JOIN indice i ON i.id = ri.indice_id
           LEFT JOIN usuario u ON u.id = ri.verificado_por
           WHERE ri.revista_id = ? ORDER BY i.orden, ri.desde""", [rid])


def indices_en(rid: int, anio: int) -> list[dict]:
    """Índices en que figura la revista el año dado."""
    return [x for x in indexaciones(rid) if x["desde"] <= anio and (x["hasta"] is None or anio <= x["hasta"])]


def clasificacion(rid: int, anio: int) -> dict | None:
    """Nivel de revisión e índices de un artículo publicado en la revista ese año, según el
    catálogo. None si la revista no está verificada (rige lo declarado por el autor)."""
    r = obtener(rid)
    if not r or r["estado"] != "verificada":
        return None
    indices = indices_en(rid, anio)
    if any(x["cuenta_como_indexado"] for x in indices):
        revision = "indexado"
    elif r["arbitrada"]:
        revision = "arbitrado"
    else:
        revision = "sin_arbitraje"
    return {"revision": revision, "indices": indices,
            "nacional": sin_tildes(r["pais"] or "").lower() == sin_tildes(config.PAIS).lower()}


def indices_catalogo() -> list[dict]:
    return get_db().q("SELECT * FROM indice WHERE activo = 1 ORDER BY orden")


# --- Cambios -------------------------------------------------------------------------------------------

def _texto(v):
    return (v or "").strip() or None


def _bool(v):
    v = str(v if v is not None else "").strip()
    return int(v) if v in ("0", "1") else None


def validar(d: dict, rid: int | None = None) -> tuple[dict, list[str]]:
    errores = []
    datos = {"titulo": _texto(d.get("titulo")), "pais": _texto(d.get("pais")),
             "editorial": _texto(d.get("editorial")), "url": _texto(d.get("url")),
             "arbitrada": _bool(d.get("arbitrada")), "acceso_abierto": _bool(d.get("acceso_abierto")),
             "nota": _texto(d.get("nota"))}
    if not datos["titulo"]:
        errores.append("El título de la revista es obligatorio.")
    validos = []
    for campo in ("issn", "eissn"):
        try:
            datos[campo] = normalizar_issn(d.get(campo))
            validos.append(campo)
        except ValueError as e:
            errores.append(str(e))
            datos[campo] = _texto(d.get(campo))
    if datos.get("issn") and datos["issn"] == datos.get("eissn"):
        errores.append("El ISSN impreso y el electrónico no pueden ser iguales.")
    for campo in validos:
        if datos.get(campo):
            otra = por_issn(datos[campo])
            if otra and otra["id"] != rid:
                errores.append(f"Ya existe una revista con el ISSN {datos[campo]}: «{otra['titulo']}».")
    if datos["url"] and not re.match(r"^https?://", datos["url"]):
        errores.append("La dirección web debe empezar con http:// o https://.")
    return datos, errores


def crear(d: dict, uid: int, verificada: bool = False) -> int:
    extra = {"estado": "verificada", "verificada_por": uid} if verificada else {"estado": "pendiente"}
    rid = get_db().t.revista.insert(**d, propuesta_por=uid, **extra)["id"]
    if verificada:
        get_db().execute("UPDATE revista SET verificada_en = datetime('now') WHERE id = ?", [rid])
    return rid


def actualizar(rid: int, d: dict):
    get_db().t.revista.update(id=rid, **d)
    get_db().execute("UPDATE revista SET actualizado_en = datetime('now') WHERE id = ?", [rid])


def verificar(rid: int, uid: int, verificada: bool = True):
    if verificada:
        get_db().execute("""UPDATE revista SET estado = 'verificada', verificada_por = ?,
                            verificada_en = datetime('now') WHERE id = ?""", [uid, rid])
    else:
        get_db().execute("""UPDATE revista SET estado = 'pendiente', verificada_por = NULL,
                            verificada_en = NULL WHERE id = ?""", [rid])


def eliminar(rid: int) -> str | None:
    n = get_db().q("SELECT COUNT(*) n FROM producto WHERE revista_id = ?", [rid])[0]["n"]
    if n:
        return f"La revista tiene {n} producto(s) vinculado(s): no se puede eliminar."
    get_db().execute("DELETE FROM revista WHERE id = ?", [rid])
    return None


def validar_indexacion(d: dict) -> tuple[dict, list[str]]:
    errores = []
    indice = str(d.get("indice_id") or "")
    if not indice.isdigit() or not get_db().q("SELECT 1 FROM indice WHERE id = ?", [int(indice)]):
        errores.append("Elija el índice.")
    desde, hasta = str(d.get("desde") or "").strip(), str(d.get("hasta") or "").strip()
    if not (desde.isdigit() and 1900 <= int(desde) <= 2100):
        errores.append("Indique desde qué año figura en el índice.")
    if hasta and not (hasta.isdigit() and 1900 <= int(hasta) <= 2100):
        errores.append("El año de término no es válido.")
    elif hasta and desde.isdigit() and int(hasta) < int(desde):
        errores.append("El año de término no puede ser anterior al de inicio.")
    cuartil = (d.get("cuartil") or "").strip().upper() or None
    if cuartil and cuartil not in CUARTILES:
        errores.append("Cuartil no válido (Q1 a Q4).")
    url = _texto(d.get("evidencia_url"))
    if url and not re.match(r"^https?://", url):
        errores.append("El enlace de evidencia debe empezar con http:// o https://.")
    datos = {"indice_id": int(indice) if indice.isdigit() else None, "desde": int(desde) if desde.isdigit() else None,
             "hasta": int(hasta) if hasta.isdigit() else None, "cuartil": cuartil,
             "fuente": _texto(d.get("fuente")), "evidencia_url": url}
    return datos, errores


def agregar_indexacion(rid: int, d: dict, uid: int) -> list[str]:
    datos, errores = validar_indexacion(d)
    if errores:
        return errores
    for x in indexaciones(rid):
        if x["indice_id"] == datos["indice_id"] and x["desde"] <= (datos["hasta"] or 9999) \
                and (x["hasta"] or 9999) >= datos["desde"]:
            return [f"Se superpone con la indexación en {x['indice']} desde {x['desde']}."]
    get_db().t.revista_indice.insert(revista_id=rid, verificado_por=uid, **datos)
    return []


def quitar_indexacion(rid: int, iid: int):
    get_db().execute("DELETE FROM revista_indice WHERE id = ? AND revista_id = ?", [iid, rid])


# --- Artículos y revistas -------------------------------------------------------------------------------

TIPO_ARTICULO = "Artículo en revista"


def coincidir(issns: list[str | None], titulo: str | None) -> dict | None:
    """Revista del catálogo que corresponde a un artículo: por ISSN (impreso o electrónico) y, si no
    hay, por título idéntico (sin distinguir tildes ni mayúsculas)."""
    for i in issns or []:
        try:
            r = por_issn(normalizar_issn(i))
        except ValueError:
            continue
        if r:
            return r
    if titulo and titulo.strip():
        filas = get_db().q("SELECT * FROM revista WHERE sin_tildes(titulo) = sin_tildes(?)", [titulo.strip()])
        if len(filas) == 1:
            return filas[0]
    return None


def reclasificar(rid: int) -> int:
    """Aplica el catálogo a los artículos de la revista (nivel de revisión e índices según el año
    de cada uno). Se llama tras verificar la revista o cambiar sus indexaciones. → cuántos
    artículos cambió. Si la revista no está verificada no toca nada (rige lo declarado)."""
    db = get_db()
    cambiados = 0
    for p in db.q("""SELECT p.id, p.anio, p.revision FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
                     WHERE p.revista_id = ? AND t.nombre = ?""", [rid, TIPO_ARTICULO]):
        c = clasificacion(rid, p["anio"])
        if c is None:
            return 0
        actuales = {f["indice_id"] for f in db.q("SELECT indice_id FROM producto_indice WHERE producto_id = ?", [p["id"]])}
        # Como al guardar: los índices se registran solo en los artículos indexados.
        nuevos = {x["indice_id"] for x in c["indices"]} if c["revision"] == "indexado" else set()
        if c["revision"] != p["revision"] or actuales != nuevos:
            with db.conn:
                db.execute("UPDATE producto SET revision = ? WHERE id = ?", [c["revision"], p["id"]])
                db.execute("DELETE FROM producto_indice WHERE producto_id = ?", [p["id"]])
                for i in nuevos:
                    db.t.producto_indice.insert(producto_id=p["id"], indice_id=i)
            cambiados += 1
    return cambiados


def sin_vincular() -> list[dict]:
    """Artículos en revista sin revista del catálogo, agrupados por el nombre declarado
    (sin distinguir tildes ni mayúsculas). Cada grupo: medio, n, productos (id, titulo, anio)."""
    grupos = {}
    for p in get_db().q("""SELECT p.id, p.titulo, p.anio, p.medio FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
                           WHERE t.nombre = ? AND p.revista_id IS NULL ORDER BY p.anio DESC""", [TIPO_ARTICULO]):
        clave = sin_tildes((p["medio"] or "").strip()) or "(sin revista declarada)"
        g = grupos.setdefault(clave, {"clave": clave, "medio": p["medio"] or "", "productos": []})
        g["productos"].append(p)
    res = sorted(grupos.values(), key=lambda g: (-len(g["productos"]), g["clave"]))
    for g in res:
        g["n"] = len(g["productos"])
        g["sugerida"] = coincidir([], g["medio"]) if g["medio"] else None
    return res


def vincular(producto_ids: list[int], rid: int) -> int:
    """Vincula artículos a una revista del catálogo (el nombre del medio pasa a ser el de la revista)
    y aplica su clasificación si está verificada."""
    r = obtener(rid)
    if not r or not producto_ids:
        return 0
    marcas = ",".join("?" * len(producto_ids))
    get_db().execute(f"UPDATE producto SET revista_id = ?, medio = ? WHERE id IN ({marcas})", [rid, r["titulo"], *producto_ids])
    reclasificar(rid)
    return len(producto_ids)
