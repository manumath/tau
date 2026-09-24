"""Carga el catálogo MSC2020 (catalogos/MSC2020.tsv) en la tabla msc.

fastmigrate lo ejecuta como: python 0004-msc2020.py <ruta_bd>
"""
import csv
import re
import sqlite3
import sys
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent.parent / "catalogos" / "MSC2020.tsv"


def nivel(codigo: str) -> int:
    if codigo.endswith("-XX"):
        return 1
    if codigo.endswith("xx"):
        return 2
    return 3


def texto_plano(texto: str) -> str:
    """'\\(\\zeta(s)\\), \\(\\mbox{GL}(2)\\)' → 'zeta(s), GL(2)' (aproximado; solo para buscar)."""
    t = re.sub(r"\\(?:mbox|mathrm|mathbb|mathcal|text|operatorname)\{([^}]*)\}", r"\1", texto)
    t = re.sub(r"\\[()\[\]]", "", t)                    # delimitadores \( \) \[ \]
    t = re.sub(r"\\[lc]?dots\b", "...", t)
    t = re.sub(r"\\([a-zA-Z]+)\s?", r"\1 ", t)          # \zeta → zeta, \infty → infty
    t = re.sub(r"[{}^_\\]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def main(ruta_bd: str):
    with open(ARCHIVO, encoding="utf-8", newline="") as f:
        filas = [(r["code"], nivel(r["code"]), r["text"], texto_plano(r["text"]), r["description"])
                 for r in csv.DictReader(f, delimiter="\t")]
    con = sqlite3.connect(ruta_bd)
    with con:
        con.executemany("INSERT INTO msc (codigo, nivel, texto, texto_plano, descripcion) "
                        "VALUES (?, ?, ?, ?, ?)", filas)
    con.close()
    print(f"MSC2020: {len(filas)} códigos cargados")


if __name__ == "__main__":
    main(sys.argv[1])
