"""Cohortes de ingreso, egreso y titulación de la licenciatura (PLAN §49).

Alimenta el tablero de cohortes y las hojas 3 a 6 de la Guía de Antecedentes de IAC-CINDA. Cuenta a
los estudiantes del programa propio con cohorte de ingreso (`estudiante.cohorte_anio`). Un
estudiante estuvo matriculado desde su cohorte hasta su último ciclo matriculado (vacío = sigue
cursando); los congelamientos intermedios no se registran.

Ciclo: semestre I (enero a julio) o II (agosto a diciembre). Se identifica por su ordinal
`anio * 2 + (0 si I, 1 si II)` para poder contar y comparar.
"""
from datetime import date

from app.comun.db import get_db

ESTADOS = {"cursando": "Cursando", "egresado": "Egresado(a)", "titulado": "Titulado(a)", "retirado": "Retirado(a)",
           "congelado": "Congelado(a)"}
MODALIDADES = {"tesis": "Tesis de grado", "proyecto_grado": "Proyecto de grado", "trabajo_dirigido": "Trabajo dirigido",
               "examen_grado": "Examen de grado", "excelencia": "Excelencia", "otra": "Otra"}
MOTIVOS = {"academico": "Académico", "no_academico": "No académico"}
TRAMOS_EDAD = ((18, "≤ 18"), (21, "19 a 21"), (25, "22 a 25"), (None, "> 25"))


def ordinal(anio: int, ciclo: str) -> int:
    return anio * 2 + (0 if ciclo == "I" else 1)


def desde_ordinal(n: int) -> tuple[int, str]:
    return n // 2, "I" if n % 2 == 0 else "II"


def texto(anio: int, ciclo: str) -> str:
    return f"{anio}-{ciclo}"


def ciclo_de(fecha_iso: str) -> tuple[int, str]:
    """Ciclo al que pertenece una fecha AAAA-MM-DD."""
    return int(fecha_iso[:4]), "I" if int(fecha_iso[5:7]) <= 7 else "II"


def ciclo_actual() -> tuple[int, str]:
    return ciclo_de(date.today().isoformat())


def alumnos() -> list[dict]:
    """Estudiantes de licenciatura del programa propio con cohorte, con sus ordinales calculados."""
    filas = get_db().q(
        """SELECT * FROM estudiante WHERE nivel = 'licenciatura' AND del_programa = 1 AND cohorte_anio IS NOT NULL
           ORDER BY cohorte_anio, cohorte_ciclo, id""")
    for f in filas:
        f["ingreso"] = ordinal(f["cohorte_anio"], f["cohorte_ciclo"])
        f["ultimo"] = ordinal(f["ultimo_anio"], f["ultimo_ciclo"]) if f["ultimo_anio"] else None
        f["egreso"] = ordinal(*ciclo_de(f["fecha_egreso"])) if f["fecha_egreso"] else None
        f["titulacion"] = ordinal(*ciclo_de(f["fecha_titulacion"])) if f["fecha_titulacion"] else None
    return filas


def matriculado(e: dict, ciclo: int, actual: int) -> bool:
    """¿Estaba matriculado en el ciclo (ordinal)? Quien sigue cursando lo está hasta el ciclo actual."""
    if ciclo < e["ingreso"]:
        return False
    fin = e["ultimo"] if e["ultimo"] is not None else actual
    return ciclo <= fin


def desertor(e: dict, actual: int) -> bool:
    """Deserción según IAC-CINDA: abandonó el programa, o congeló sus estudios y no volvió en los dos ciclos siguientes."""
    return e["estado"] == "retirado" or (e["estado"] == "congelado" and e["ultimo"] is not None
                                          and actual > e["ultimo"] + 2)


def cohortes_hasta(ultimo: tuple[int, str], n: int) -> list[int]:
    """Los `n` ciclos (ordinales) que terminan en `ultimo`, del más antiguo al más reciente."""
    fin = ordinal(*ultimo)
    return list(range(fin - n + 1, fin + 1))


def resumen(ciclos: list[int], alumnos_: list[dict] | None = None) -> list[dict]:
    """Una entrada por cohorte (ciclo de ingreso) en `ciclos`, con sus conteos:
    n (ingresantes), matricula (por ciclo de `ciclos`), egresados y titulados (por ciclo de `ciclos`),
    desertores (por motivo) y estados actuales."""
    actual = ordinal(*ciclo_actual())
    todos = alumnos_ if alumnos_ is not None else alumnos()
    res = []
    for c in ciclos:
        grupo = [e for e in todos if e["ingreso"] == c]
        desertores = [e for e in grupo if desertor(e, actual)]
        res.append({
            "ciclo": c, "texto": texto(*desde_ordinal(c)), "n": len(grupo), "alumnos": grupo,
            "matricula": [sum(matriculado(e, k, actual) for e in grupo) for k in ciclos],
            "egresados": [sum(1 for e in grupo if e["egreso"] == k) for k in ciclos],
            "titulados": [sum(1 for e in grupo if e["titulacion"] == k) for k in ciclos],
            "desertores": len(desertores),
            "desercion_academica": sum(e["motivo_retiro"] == "academico" for e in desertores),
            "desercion_no_academica": sum(e["motivo_retiro"] != "academico" for e in desertores),
            "estados": {k: sum(e["estado"] == k for e in grupo) for k in ESTADOS},
        })
    return res


def admision(ciclo: int, alumnos_: list[dict] | None = None) -> dict:
    """Matrícula de primer año de la cohorte (hoja 3). Sin dato de vía de ingreso = ordinaria."""
    grupo = [e for e in (alumnos_ if alumnos_ is not None else alumnos()) if e["ingreso"] == ciclo]
    tramos = [0] * len(TRAMOS_EDAD)
    for e in grupo:
        if e["edad_ingreso"] is not None:
            tramos[next(i for i, (tope, _) in enumerate(TRAMOS_EDAD) if tope is None or e["edad_ingreso"] <= tope)] += 1
    return {
        "ordinaria": sum(e["via_ingreso"] != "especial" for e in grupo),
        "especial": sum(e["via_ingreso"] == "especial" for e in grupo),
        "hombres": sum(e["sexo"] == "hombre" for e in grupo), "mujeres": sum(e["sexo"] == "mujer" for e in grupo),
        "otra_ciudad": sum(bool(e["otra_ciudad"]) for e in grupo), "extranjeros": sum(bool(e["extranjero"]) for e in grupo),
        "publico": sum(e["colegio"] == "publico" for e in grupo), "privado": sum(e["colegio"] == "privado" for e in grupo),
        "tramos": tramos,
    }


def tasa(parte: int, total: int) -> float | None:
    return parte / total if total else None


def indicadores(alumnos_: list[dict] | None = None) -> dict:
    """Totales de todas las cohortes: para el encabezado del tablero."""
    todos = alumnos_ if alumnos_ is not None else alumnos()
    estados = {k: sum(e["estado"] == k for e in todos) for k in ESTADOS}
    titulados = [e for e in todos if e["titulacion"] is not None]
    anios = [(e["titulacion"] - e["ingreso"]) / 2 for e in titulados]
    actual = ordinal(*ciclo_actual())
    return {"total": len(todos), "estados": estados, "desertores": sum(desertor(e, actual) for e in todos),
            "anios_a_titulacion": sum(anios) / len(anios) if anios else None}
