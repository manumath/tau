"""Carga del marco de calidad desde CSV (PLAN §57, etapa 2; formato en datos/calidad/marco-carrera/README.md).

Solo usa la conexión que recibe (`execute` y `fetchall`), sin importar el resto de la aplicación: así la llama
también la migración 0051, que corre en un proceso aparte. Las columnas de cada archivo (`COLUMNAS`) son también
las de las hojas del XLSX que exporta la pantalla del marco, para que lo exportado se pueda volver a cargar.
"""
import csv
from pathlib import Path

from app.comun import config


CARPETA = config.INSTANCIA / "calidad" / "marco-carrera"     # el marco de la instancia de esta instalación (PLAN §74)

COLUMNAS = {
    "escala": ["valor", "nombre", "descripcion"],
    "atributos": ["clave", "nombre", "descripcion"],
    "dimensiones": ["codigo", "nombre", "descripcion", "referencia"],
    "criterios": ["dimension", "codigo", "nombre", "descripcion"],
    "indicadores": ["criterio", "codigo", "nombre", "tipo", "formula", "fuente", "unidad_medida", "frecuencia",
                    "sentido", "responsable", "referencia", "atributos"],
}
CAMPOS_MARCO = ("nombre", "version", "descripcion", "vigente_desde", "ventana_anios")


def _leer(carpeta: Path, nombre: str) -> list[dict]:
    with open(carpeta / f"{nombre}.csv", encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in fila.items()} for fila in csv.DictReader(f)]


def _uno(con, sql, params=()):
    filas = con.execute(sql, params).fetchall()
    return filas[0][0] if filas else None


def _insertar(con, sql, params) -> int:
    con.execute(sql, params)
    return _uno(con, "SELECT last_insert_rowid()")


def _o_nulo(v):
    return v if v not in ("", None) else None


def cargar_carpeta(con, carpeta: Path = CARPETA) -> int | None:
    """Crea el marco de la Carrera con los CSV de `carpeta`. Si esa versión ya existe, no hace nada (→ None).
    Un código desconocido (dimensión de un criterio, criterio de un indicador o atributo) es un error: ValueError."""
    datos = {f["campo"]: f["valor"] for f in _leer(carpeta, "marco")}
    unidad = _uno(con, "SELECT id FROM unidad WHERE tipo = 'carrera' ORDER BY id LIMIT 1")
    if unidad is None:
        raise ValueError("No existe una unidad de tipo carrera")
    if _uno(con, "SELECT id FROM marco_calidad WHERE unidad_id = ? AND version = ?", (unidad, datos["version"])):
        return None
    mid = _insertar(con, "INSERT INTO marco_calidad (unidad_id, nombre, version, descripcion, vigente_desde, "
                         "ventana_anios) VALUES (?, ?, ?, ?, ?, ?)",
                    (unidad, datos["nombre"], datos["version"], _o_nulo(datos.get("descripcion")),
                     _o_nulo(datos.get("vigente_desde")), int(datos.get("ventana_anios") or 5)))
    for n in _leer(carpeta, "escala"):
        con.execute("INSERT INTO nivel_escala (marco_id, valor, nombre, descripcion) VALUES (?, ?, ?, ?)",
                    (mid, int(n["valor"]), n["nombre"], _o_nulo(n["descripcion"])))
    atributos = {}
    for a in _leer(carpeta, "atributos"):
        atributos[a["clave"]] = _insertar(
            con, "INSERT INTO atributo_calidad (marco_id, clave, nombre, descripcion) VALUES (?, ?, ?, ?)",
            (mid, a["clave"], a["nombre"], _o_nulo(a["descripcion"])))
    dimensiones = {}
    for d in _leer(carpeta, "dimensiones"):
        dimensiones[d["codigo"]] = _insertar(
            con, "INSERT INTO dimension_calidad (marco_id, codigo, nombre, descripcion, referencia) VALUES (?, ?, ?, ?, ?)",
            (mid, d["codigo"], d["nombre"], _o_nulo(d["descripcion"]), _o_nulo(d["referencia"])))
    criterios = {}
    for c in _leer(carpeta, "criterios"):
        if c["dimension"] not in dimensiones:
            raise ValueError(f"Criterio {c['codigo']}: no existe la dimensión {c['dimension']}")
        criterios[c["codigo"]] = _insertar(
            con, "INSERT INTO criterio_calidad (dimension_id, codigo, nombre, descripcion) VALUES (?, ?, ?, ?)",
            (dimensiones[c["dimension"]], c["codigo"], c["nombre"], _o_nulo(c["descripcion"])))
    for i in _leer(carpeta, "indicadores"):
        if i["criterio"] not in criterios:
            raise ValueError(f"Indicador {i['codigo']}: no existe el criterio {i['criterio']}")
        iid = _insertar(
            con, "INSERT INTO indicador_calidad (criterio_id, codigo, nombre, tipo, formula, fuente, unidad_medida, "
                 "frecuencia, sentido, responsable, referencia) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (criterios[i["criterio"]], i["codigo"], i["nombre"], i["tipo"], _o_nulo(i["formula"]),
             i["fuente"] or "manual", _o_nulo(i["unidad_medida"]), i["frecuencia"] or "anual", i["sentido"] or "mayor",
             _o_nulo(i["responsable"]), _o_nulo(i["referencia"])))
        for clave in filter(None, (x.strip() for x in i["atributos"].split("|"))):
            if clave not in atributos:
                raise ValueError(f"Indicador {i['codigo']}: no existe el atributo {clave}")
            con.execute("INSERT INTO indicador_atributo (indicador_id, atributo_id) VALUES (?, ?)",
                        (iid, atributos[clave]))
    return mid
