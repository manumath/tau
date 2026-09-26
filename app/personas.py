"""Personas que figuran como autores o participantes: investigadores del instituto y externos.

En formularios y datos se identifican con una referencia de texto: 'i:<usuario_id>' para
investigadores e 'e:<persona_externa_id>' para externos. Los externos que llegan de una
importación y aún no existen viajan como 'n:<datos codificados>' y se registran recién al
guardar (`materializar`), para no dejar personas huérfanas si se cancela el formulario.
"""
import base64
import json

from app import paises
from app.db import get_db, sin_tildes


def ref(investigador_id=None, externo_id=None) -> str:
    return f"i:{investigador_id}" if investigador_id else f"e:{externo_id}"


def parsear_ref(texto: str) -> tuple[str, int] | None:
    """'i:3' → ('i', 3). None si el formato no es válido (las 'n:' no tienen id todavía)."""
    tipo, _, num = (texto or "").partition(":")
    if tipo in ("i", "e") and num.isdigit():
        return tipo, int(num)
    return None


def ref_nueva(nombres: str, apellidos: str, afiliacion: str | None, pais: str | None = None) -> str:
    datos = json.dumps({"n": nombres, "a": apellidos, "f": afiliacion, "p": pais}, ensure_ascii=False)
    return "n:" + base64.urlsafe_b64encode(datos.encode()).decode()


def _datos_nueva(r: str) -> dict | None:
    try:
        d = json.loads(base64.urlsafe_b64decode(r[2:].encode()).decode())
        return {"nombres": str(d["n"])[:100], "apellidos": str(d["a"])[:100],
                "afiliacion": (str(d["f"])[:200] if d.get("f") else None),
                "pais": (str(d["p"])[:80] if d.get("p") else None)}
    except (ValueError, KeyError, TypeError):
        return None


def materializar(r: str, creado_por: int) -> str:
    """'n:…' → 'e:<id>' (reutiliza un externo con el mismo nombre si ya existe). Las demás
    referencias se devuelven tal cual."""
    if not (r or "").startswith("n:") or not (d := _datos_nueva(r)) or not d["apellidos"]:
        return r
    existente = externo_similar(d["nombres"], d["apellidos"])
    if existente:
        completar_pais(existente, d.get("pais") or paises.desde_texto(d["afiliacion"]))
    else:
        existente = crear_externo(d["nombres"] or "—", d["apellidos"], d["afiliacion"], d.get("pais"), creado_por)
    return f"e:{existente['id']}"


def completar_pais(externo: dict, pais: str | None):
    """Si al externo le falta el país y ahora se conoce, se completa (nunca se sobrescribe)."""
    if pais and not externo.get("pais"):
        get_db().execute("UPDATE persona_externa SET pais = ? WHERE id = ? AND (pais IS NULL OR pais = '')",
                         [paises.normalizar(pais), externo["id"]])


def columnas(r: str) -> dict:
    """Referencia → columnas investigador_id / externo_id."""
    tipo, num = parsear_ref(r)
    return {"investigador_id": num if tipo == "i" else None,
            "externo_id": num if tipo == "e" else None}


def por_ref(r: str) -> dict | None:
    """Datos para mostrar una persona: nombre, afiliación y si es interna."""
    if (r or "").startswith("n:"):
        d = _datos_nueva(r)
        return {**d, "id": None, "ref": r, "interno": False, "nueva": True} if d else None
    p = parsear_ref(r)
    if not p:
        return None
    tipo, num = p
    if tipo == "i":
        filas = get_db().q(
            """SELECT u.id, u.nombres, u.apellidos, i.unidad AS afiliacion FROM usuario u
               JOIN investigador i ON i.usuario_id = u.id WHERE u.id = ?""", [num])
    else:
        filas = get_db().q("SELECT id, nombres, apellidos, institucion AS afiliacion "
                           "FROM persona_externa WHERE id = ?", [num])
    if not filas:
        return None
    return {**filas[0], "ref": r, "interno": tipo == "i"}


def buscar(texto: str, excluir: set[str] = frozenset(), limite: int = 8) -> list[dict]:
    """Investigadores (primero) y externos cuyo nombre coincide; excluye referencias dadas."""
    patron = f"%{sin_tildes(texto.strip())}%"
    if len(texto.strip()) < 2:
        return []
    internos = get_db().q(
        """SELECT u.id, u.nombres, u.apellidos, i.unidad AS afiliacion FROM usuario u
           JOIN investigador i ON i.usuario_id = u.id
           WHERE u.activo = 1 AND (sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p
                                   OR sin_tildes(u.apellidos || ' ' || u.nombres) LIKE :p)
           ORDER BY sin_tildes(u.apellidos) LIMIT :l""", {"p": patron, "l": limite})
    externos = get_db().q(
        """SELECT id, nombres, apellidos, institucion AS afiliacion FROM persona_externa
           WHERE usuario_id IS NULL AND (sin_tildes(nombres || ' ' || apellidos) LIKE :p
                                         OR sin_tildes(apellidos || ' ' || nombres) LIKE :p)
           ORDER BY sin_tildes(apellidos) LIMIT :l""", {"p": patron, "l": limite})
    res = [{**p, "ref": f"i:{p['id']}", "interno": True} for p in internos]
    res += [{**p, "ref": f"e:{p['id']}", "interno": False} for p in externos]
    return [p for p in res if p["ref"] not in excluir][:limite]


def crear_externo(nombres: str, apellidos: str, institucion: str | None, pais: str | None,
                  creado_por: int) -> dict:
    """El país se normaliza («USA» → «Estados Unidos») y, si falta, se deduce de la institución."""
    institucion = (institucion or "").strip() or None
    pais = paises.normalizar(pais) or paises.desde_texto(institucion)
    return get_db().t.persona_externa.insert(
        nombres=nombres.strip(), apellidos=apellidos.strip(), institucion=institucion, pais=pais,
        creado_por=creado_por)


def externo_similar(nombres: str, apellidos: str) -> dict | None:
    """Externo ya registrado con el mismo nombre (ignora tildes y mayúsculas)."""
    filas = get_db().q(
        """SELECT * FROM persona_externa WHERE sin_tildes(nombres) = sin_tildes(?)
           AND sin_tildes(apellidos) = sin_tildes(?) LIMIT 1""", [nombres.strip(), apellidos.strip()])
    return filas[0] if filas else None


def nombre_cita(p: dict) -> str:
    """'Emmy Noether' → 'Noether, E.'; 'Carl Friedrich' → 'Gauss, C. F.'"""
    iniciales = " ".join(f"{n[0]}." for n in p["nombres"].replace("-", " ").split() if n)
    return f"{p['apellidos']}, {iniciales}"


# --- Coautores externos: país e institución (internacionalización) -----------------------------------------------

def externos(texto: str = "", solo_sin_pais: bool = False) -> list[dict]:
    """Personas externas (sin cuenta) con cuántos productos, actividades y proyectos tienen."""
    patron = f"%{sin_tildes(texto.strip())}%"
    return get_db().q(
        """SELECT pe.*,
                  (SELECT COUNT(*) FROM producto_autor x WHERE x.externo_id = pe.id) AS n_productos,
                  (SELECT COUNT(*) FROM actividad_participante x WHERE x.externo_id = pe.id) AS n_actividades,
                  (SELECT COUNT(*) FROM proyecto_participante x WHERE x.externo_id = pe.id) AS n_proyectos
           FROM persona_externa pe WHERE pe.usuario_id IS NULL
             AND (:t = '' OR sin_tildes(pe.nombres || ' ' || pe.apellidos) LIKE :p
                  OR sin_tildes(pe.apellidos || ' ' || pe.nombres) LIKE :p OR sin_tildes(pe.institucion) LIKE :p)
             AND (:s = 0 OR pe.pais IS NULL OR pe.pais = '')
           ORDER BY (pe.pais IS NULL OR pe.pais = '') DESC, n_productos DESC, sin_tildes(pe.apellidos) LIMIT 300""",
        {"t": texto.strip(), "p": patron, "s": int(solo_sin_pais)})


def actualizar_externo(eid: int, institucion: str | None, pais: str | None):
    get_db().execute("UPDATE persona_externa SET institucion = ?, pais = ? WHERE id = ?",
                     [(institucion or "").strip() or None, paises.normalizar(pais), eid])


def completar_paises() -> tuple[int, int]:
    """Normaliza los países escritos («USA» → «Estados Unidos») y deduce los que faltan desde la
    institución. → (normalizados, deducidos)."""
    normalizados = deducidos = 0
    for e in get_db().q("SELECT id, institucion, pais FROM persona_externa"):
        if e["pais"]:
            nuevo = paises.normalizar(e["pais"])
            if nuevo != e["pais"]:
                get_db().execute("UPDATE persona_externa SET pais = ? WHERE id = ?", [nuevo, e["id"]])
                normalizados += 1
        elif (nuevo := paises.desde_texto(e["institucion"])):
            get_db().execute("UPDATE persona_externa SET pais = ? WHERE id = ?", [nuevo, e["id"]])
            deducidos += 1
    return normalizados, deducidos
