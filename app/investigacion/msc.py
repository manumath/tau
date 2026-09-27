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
