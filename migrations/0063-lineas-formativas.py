"""Línea formativa y área de cada asignatura (PLAN §61, 8-nov-2026).

La línea formativa (Álgebra, Análisis, Fundamentos y Matemática Discreta…) y el área o la línea de investigación con
que se relaciona cada asignatura son propias de la asignatura, no del plan: van en `asignatura`. Se cargan de
`datos/planes/lineas-formativas.csv`; una sigla que no está en el archivo queda sin línea.

fastmigrate lo ejecuta como: python 0063-lineas-formativas.py <ruta_bd>
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.academico import importar_planes  # noqa: E402  (no importa el resto de la aplicación)


def main(ruta_bd: str):
    con = sqlite3.connect(ruta_bd)
    with con:
        con.execute("ALTER TABLE asignatura ADD COLUMN linea_formativa TEXT")
        con.execute("ALTER TABLE asignatura ADD COLUMN area_id INTEGER REFERENCES area_investigacion(id)")
        con.execute("ALTER TABLE asignatura ADD COLUMN linea_id INTEGER REFERENCES linea_investigacion(id)")
        importar_planes.cargar_lineas_formativas(con)
    con.close()


if __name__ == "__main__":
    main(sys.argv[1])
