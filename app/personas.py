"""Personas que figuran como autores o participantes: investigadores del instituto y externos.

En formularios y datos se identifican con una referencia de texto: 'i:<usuario_id>' para
investigadores e 'e:<persona_externa_id>' para externos. Los externos que llegan de una
importación y aún no existen viajan como 'n:<datos codificados>' y se registran recién al
guardar (`materializar`), para no dejar personas huérfanas si se cancela el formulario.
"""
import base64
import json

from app.db import get_db, sin_tildes


def ref(investigador_id=None, externo_id=None) -> str:
    return f"i:{investigador_id}" if investigador_id else f"e:{externo_id}"


def parsear_ref(texto: str) -> tuple[str, int] | None:
    """'i:3' → ('i', 3). None si el formato no es válido (las 'n:' no tienen id todavía)."""
    tipo, _, num = (texto or "").partition(":")
    if tipo in ("i", "e") and num.isdigit():
        return tipo, int(num)
    return None


def ref_nueva(nombres: str, apellidos: str, afiliacion: str | None) -> str:
    datos = json.dumps({"n": nombres, "a": apellidos, "f": afiliacion}, ensure_ascii=False)
    return "n:" + base64.urlsafe_b64encode(datos.encode()).decode()


def _datos_nueva(r: str) -> dict | None:
    try:
        d = json.loads(base64.urlsafe_b64decode(r[2:].encode()).decode())
        return {"nombres": str(d["n"])[:100], "apellidos": str(d["a"])[:100],
                "afiliacion": (str(d["f"])[:200] if d.get("f") else None)}
    except (ValueError, KeyError, TypeError):
        return None


def materializar(r: str, creado_por: int) -> str:
    """'n:…' → 'e:<id>' (reutiliza un externo con el mismo nombre si ya existe). Las demás
    referencias se devuelven tal cual."""
    if not (r or "").startswith("n:") or not (d := _datos_nueva(r)) or not d["apellidos"]:
        return r
    existente = externo_similar(d["nombres"], d["apellidos"]) or crear_externo(
        d["nombres"] or "—", d["apellidos"], d["afiliacion"], None, creado_por)
    return f"e:{existente['id']}"


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
    return get_db().t.persona_externa.insert(
        nombres=nombres.strip(), apellidos=apellidos.strip(),
        institucion=(institucion or "").strip() or None, pais=(pais or "").strip() or None,
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
