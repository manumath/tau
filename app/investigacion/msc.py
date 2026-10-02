"""Consultas al catálogo MSC2020."""
import re

from app.comun.db import get_db


def por_codigo(codigo: str) -> dict | None:
    filas = get_db().q("SELECT * FROM msc WHERE codigo = ?", [codigo])
    return filas[0] if filas else None


def buscar(texto: str, limite: int = 12, excluir: tuple = ()) -> list[dict]:
    """Busca por código ('11M', '11-XX') o por palabras del texto ('zeta', 'graph coloring').

    Primero van las coincidencias de código y, entre ellas, las más generales (sección antes
    que subsección y que código fino), para que escribir '11' muestre primero 'Number theory'.
    """
    texto = texto.strip()
    if not texto:
        return []
    excl = list(excluir) or [""]
    marcas = ",".join("?" * len(excl))
    if re.fullmatch(r"\d{2}[A-Za-z0-9\-]{0,3}", texto):
        return get_db().q(
            f"""SELECT * FROM msc WHERE codigo LIKE ? AND codigo NOT IN ({marcas})
                ORDER BY nivel, codigo LIMIT ?""",
            [texto.upper().replace("X", "_") + "%", *excl, limite])
    palabras = texto.split()[:6]
    condiciones = " AND ".join("texto_plano LIKE ?" for _ in palabras)
    return get_db().q(
        f"""SELECT * FROM msc WHERE {condiciones} AND codigo NOT IN ({marcas})
            ORDER BY nivel, length(texto_plano), codigo LIMIT ?""",
        [*(f"%{p}%" for p in palabras), *excl, limite])


def seccion(codigo: str) -> dict | None:
    """Sección de nivel 1 a la que pertenece un código: '11M06' → '11-XX'."""
    return por_codigo(f"{codigo[:2]}-XX")


# --- Clasificación de los productos --------------------------------------------------------
# Un código principal (orden 0) y hasta MAX_PRODUCTO - 1 secundarios, de cualquier nivel (PLAN.md §45).

MAX_PRODUCTO = 5


def de_producto(pid: int) -> list[dict]:
    """Códigos del producto en orden; el primero es el principal."""
    return get_db().q(
        """SELECT m.*, pm.orden = 0 AS principal FROM producto_msc pm JOIN msc m ON m.codigo = pm.codigo
           WHERE pm.producto_id = ? ORDER BY pm.orden""", [pid])


def validar(codigos: list[str]) -> tuple[list[str], list[str]]:
    """→ (códigos limpios en orden, errores)."""
    limpios = [c.strip() for c in codigos or [] if c and c.strip()]
    errores = []
    if len(set(limpios)) != len(limpios):
        errores.append("Hay códigos MSC repetidos.")
    if len(limpios) > MAX_PRODUCTO:
        errores.append(f"Indique a lo sumo {MAX_PRODUCTO} códigos MSC: uno principal y hasta "
                       f"{MAX_PRODUCTO - 1} secundarios.")
    if limpios and len(get_db().q(f"SELECT codigo FROM msc WHERE codigo IN ({','.join('?' * len(limpios))})",
                                  limpios)) != len(set(limpios)):
        errores.append("Hay códigos MSC que no existen en el catálogo MSC2020.")
    return limpios, errores


def guardar_de_producto(pid: int, codigos: list[str]):
    db = get_db()
    db.execute("DELETE FROM producto_msc WHERE producto_id = ?", [pid])
    for orden, c in enumerate(codigos):
        db.t.producto_msc.insert(producto_id=pid, codigo=c, orden=orden)


def existentes(codigos: list[str]) -> list[str]:
    """Los códigos que están en el catálogo, en el mismo orden y sin repetir."""
    validos = {f["codigo"] for f in get_db().q(
        f"SELECT codigo FROM msc WHERE codigo IN ({','.join('?' * len(codigos)) or 'NULL'})", list(codigos))}
    vistos = []
    for c in codigos:
        if c in validos and c not in vistos:
            vistos.append(c)
    return vistos


def sugeridos_por_perfil(uids: list[int]) -> list[str]:
    """Áreas principales de los perfiles de esas personas (en ese orden), para sugerir una clasificación."""
    codigos = []
    for uid in uids:
        filas = get_db().q("SELECT codigo FROM investigador_msc WHERE usuario_id = ? AND principal = 1", [uid])
        if filas and filas[0]["codigo"] not in codigos:
            codigos.append(filas[0]["codigo"])
    return codigos[:MAX_PRODUCTO]


def secciones() -> list[dict]:
    """Secciones (nivel 1) del catálogo: '11-XX Number theory'…"""
    return get_db().q("SELECT * FROM msc WHERE nivel = 1 ORDER BY codigo")
