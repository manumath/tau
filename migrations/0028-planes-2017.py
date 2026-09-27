"""Carga los planes de estudio 2017 (datos/planes/) y marca sus inconsistencias para revisión.

fastmigrate lo ejecuta como: python 0028-planes-2017.py <ruta_bd>
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.academico import importar_planes  # noqa: E402  (no importa el resto de la aplicación)


def main(ruta_bd: str):
    con = sqlite3.connect(ruta_bd)
    with con:
        importar_planes.cargar_carpeta(con)
    con.close()


if __name__ == "__main__":
    main(sys.argv[1])
