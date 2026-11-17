"""Carga de una **instancia** en una base nueva (PLAN §74): los datos y la marca de una unidad viven en una carpeta
fuera del código y aquí se llevan a la base.

    instancias/<nombre>/
      instancia.toml     nombre, perfil de módulos y textos propios de la unidad
      unidades.csv       tipo, sigla, nombre (universidad, facultad, carrera, instituto)
      catalogos/         areas.csv, lineas.csv y, si la unidad lo usa, MSC2020.tsv
      planes/            planes de estudio (formato en su README)
      calidad/           marco de calidad (marco-carrera/) y, para subirlo después en pantalla, el plan de mejora
      marca/             colores e imágenes (app/comun/marca.py)

El esquema base (`migrations/0001-esquema.sql`) no trae datos de ninguna unidad: sin instancia, el sistema arranca con
cuatro unidades genéricas y los catálogos vacíos. Cada paso carga solo lo que falta, así que repetir la carga no
duplica. Trabaja con una conexión `sqlite3` propia, como las migraciones, y la cierra antes de que la aplicación abra
la base. Junta importadores de varios paquetes: por eso vive aquí y no en `app/comun`.
"""
import csv
import re
import sqlite3
import tomllib
from pathlib import Path

from app.academico import importar_planes
from app.calidad import marco_csv
from app.comun import config

TIPOS_UNIDAD = ("universidad", "facultad", "carrera", "instituto")


def leer_toml(carpeta: Path) -> dict:
    archivo = Path(carpeta) / "instancia.toml"
    return tomllib.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}


def _csv(archivo: Path, **kw) -> list[dict]:
    if not archivo.exists():
        return []
    with open(archivo, encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in fila.items()} for fila in csv.DictReader(f, **kw)]


def _uno(con, sql, params=()):
    filas = con.execute(sql, params).fetchall()
    return filas[0][0] if filas else None


def cargar_unidades(con, carpeta: Path) -> int:
    """Sigla y nombre de cada unidad (`unidades.csv`: tipo, sigla, nombre). Los ids no cambian."""
    n = 0
    for u in _csv(carpeta / "unidades.csv"):
        if u["tipo"] not in TIPOS_UNIDAD:
            raise ValueError(f"unidades.csv: tipo de unidad desconocido «{u['tipo']}».")
        con.execute("UPDATE unidad SET sigla = ?, nombre = ? WHERE tipo = ?", (u["sigla"], u["nombre"], u["tipo"]))
        n += 1
    return n


def cargar_areas_y_lineas(con, carpeta: Path) -> int:
    """Áreas y líneas de investigación (`catalogos/areas.csv`: nombre, orden; `catalogos/lineas.csv`: area, nombre,
    orden, descripcion, vigente_desde, vigente_hasta). Las que ya existen, por nombre, no se tocan."""
    n = 0
    for a in _csv(carpeta / "catalogos" / "areas.csv"):
        if not _uno(con, "SELECT 1 FROM area_investigacion WHERE lower(nombre) = lower(?)", (a["nombre"],)):
            con.execute("INSERT INTO area_investigacion (nombre, orden) VALUES (?, ?)", (a["nombre"], int(a["orden"] or 0)))
            n += 1
    for x in _csv(carpeta / "catalogos" / "lineas.csv"):
        if _uno(con, "SELECT 1 FROM linea_investigacion WHERE lower(nombre) = lower(?)", (x["nombre"],)):
            continue
        area = _uno(con, "SELECT id FROM area_investigacion WHERE lower(nombre) = lower(?)", (x["area"],)) if x["area"] else None
        if x["area"] and area is None:
            raise ValueError(f"lineas.csv: la línea «{x['nombre']}» nombra un área que no existe: «{x['area']}».")
        con.execute("INSERT INTO linea_investigacion (nombre, area_id, orden, descripcion, vigente_desde, vigente_hasta) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (x["nombre"], area, int(x["orden"] or 0), x.get("descripcion") or None,
                     x.get("vigente_desde") or None, x.get("vigente_hasta") or None))
        n += 1
    return n


def _msc_nivel(codigo: str) -> int:
    return 1 if codigo.endswith("-XX") else 2 if codigo.endswith("xx") else 3


def _msc_texto_plano(texto: str) -> str:
    r"""'\(\zeta(s)\), \(\mbox{GL}(2)\)' → 'zeta(s), GL(2)' (aproximado; solo para buscar)."""
    t = re.sub(r"\\(?:mbox|mathrm|mathbb|mathcal|text|operatorname)\{([^}]*)\}", r"\1", texto)
    t = re.sub(r"\\[()\[\]]", "", t)                    # delimitadores \( \) \[ \]
    t = re.sub(r"\\[lc]?dots\b", "...", t)
    t = re.sub(r"\\([a-zA-Z]+)\s?", r"\1 ", t)          # \zeta → zeta, \infty → infty
    t = re.sub(r"[{}^_\\]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def cargar_msc(con, carpeta: Path) -> int:
    """Clasificación MSC2020 (`catalogos/MSC2020.tsv`), para las unidades de matemática. Sin el archivo, la tabla queda
    vacía y los productos no se clasifican."""
    archivo = carpeta / "catalogos" / "MSC2020.tsv"
    if not archivo.exists() or _uno(con, "SELECT 1 FROM msc LIMIT 1"):
        return 0
    filas = [(r["code"], _msc_nivel(r["code"]), r["text"], _msc_texto_plano(r["text"]), r["description"])
             for r in _csv(archivo, delimiter="\t")]
    con.executemany("INSERT INTO msc (codigo, nivel, texto, texto_plano, descripcion) VALUES (?, ?, ?, ?, ?)", filas)
    return len(filas)


def poner_en_vigencia(con, planes: list[int]) -> int:
    """Los planes de la instancia son los que rigen en la unidad: quedan vigentes, agrupados en la reforma curricular de
    su nombre («Plan 2017»), con la duración y los ciclos que muestra su malla. Un plan cargado después, desde la
    pantalla, nace en elaboración (PLAN §65)."""
    for pid in planes:
        nombre, resolucion, desde = con.execute("SELECT nombre, resolucion, vigente_desde FROM plan_estudios WHERE id = ?",
                                                (pid,)).fetchone()
        reforma = _uno(con, "SELECT id FROM reforma_curricular WHERE nombre = ?", (nombre,))
        if reforma is None:
            con.execute("INSERT INTO reforma_curricular (nombre, resolucion, vigente_desde) VALUES (?, ?, ?)",
                        (nombre, resolucion, desde))
            reforma = _uno(con, "SELECT last_insert_rowid()")
        con.execute("UPDATE plan_estudios SET reforma_id = ?, estado = 'vigente' WHERE id = ?", (reforma, pid))
        # La duración y los ciclos salen de la malla cargada (lo que hacía la migración que agregó esos datos).
        con.execute("UPDATE plan_estudios SET duracion_semestres = (SELECT MAX(semestre) FROM plan_asignatura "
                    "WHERE plan_id = plan_estudios.id) WHERE id = ?", (pid,))
        con.execute("""INSERT INTO plan_ciclo (plan_id, nombre, semestre_desde, semestre_hasta)
                       SELECT plan_id, ciclo, MIN(semestre), MAX(semestre) FROM plan_asignatura
                       WHERE plan_id = ? AND ciclo IS NOT NULL AND semestre IS NOT NULL GROUP BY plan_id, ciclo""", (pid,))
    return len(planes)


def cargar(ruta_bd: Path | str, carpeta: Path | str) -> dict:
    """Lleva la instancia de `carpeta` a la base `ruta_bd`, que ya tiene el esquema. → cuántos registros cargó cada paso."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise ValueError(f"No existe la carpeta de la instancia: {carpeta}")
    con = sqlite3.connect(ruta_bd)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        with con:
            res = {"unidades": cargar_unidades(con, carpeta), "areas y líneas": cargar_areas_y_lineas(con, carpeta),
                   "códigos MSC": cargar_msc(con, carpeta)}
            if (carpeta / "planes" / "planes.csv").exists():
                res["planes de estudio"] = poner_en_vigencia(con, importar_planes.cargar_carpeta(con, carpeta / "planes"))
                res["asignaturas con línea formativa"] = importar_planes.cargar_lineas_formativas(con, carpeta / "planes")
            if (carpeta / "calidad" / "marco-carrera" / "marco.csv").exists():
                res["marco de calidad"] = int(bool(marco_csv.cargar_carpeta(con, carpeta / "calidad" / "marco-carrera")))
    finally:
        con.close()
    return res


def base_con_instancia(ruta_bd: Path | str, carpeta: Path | str | None = None) -> dict:
    """Crea la base si no existe, le aplica el esquema y carga la instancia (lo que falte). Deja abierta la conexión de
    la aplicación, como `init_db`. `carpeta`: por omisión, la instancia de esta instalación (`config.INSTANCIA`)."""
    from app.comun.db import get_db, init_db
    init_db(ruta_bd)
    get_db().conn.close()             # la carga usa su propia conexión (sqlite3), como hacían las migraciones
    res = cargar(ruta_bd, carpeta or config.INSTANCIA)
    init_db(ruta_bd)
    return res
