"""Carga el borrador del marco de calidad de la Carrera (datos/calidad/marco-carrera/, PLAN §57, etapa 2).

Después se edita en la pantalla «Marco de calidad»; esta migración no vuelve a correr.
fastmigrate lo ejecuta como: python 0051-marco-de-la-carrera.py <ruta_bd>
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.calidad import marco_csv  # noqa: E402  (no importa el resto de la aplicación)


def main(ruta_bd: str):
    con = sqlite3.connect(ruta_bd)
    con.execute("PRAGMA foreign_keys = ON")
    with con:
        marco_csv.cargar_carpeta(con)
    con.close()


if __name__ == "__main__":
    main(sys.argv[1])
