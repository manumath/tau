"""Carga de planes de estudio desde CSV (datos/planes/) y detección de inconsistencias.

Formato (ver datos/planes/README.md):
- `planes.csv`: un plan por fila (programa, nivel, nombre del plan, resolución, vigencia, sistema de
  horas o créditos, nota mínima y los totales que declara el documento).
- un CSV por plan: una fila por asignatura o casilla de electiva (sigla, nombre, tipo, semestre,
  ciclo, horas teóricas/prácticas/laboratorio semanales o créditos, requisitos separados por «;»).
- `observaciones.csv`: inconsistencias que solo se ven leyendo el documento.

No corrige nada: carga el plan tal como está y registra en `observacion_plan` lo que no cuadra
(totales, requisitos inexistentes, asignaturas repetidas, nombres distintos para una sigla).

Solo usa la conexión que recibe (`execute` y `fetchall`), sin importar el resto de la aplicación:
así lo llama también la migración 0028, que corre en un proceso aparte.
"""
import csv
from pathlib import Path

CARPETA = Path(__file__).resolve().parents[2] / "datos" / "planes"
DEPARTAMENTO_PROPIO = "MAT"   # las demás siglas (FIS, INF…) las dicta otra unidad


def _entero(v):
    v = (v or "").strip()
    return int(v) if v else None


def _uno(con, sql, params=()):
    filas = con.execute(sql, params).fetchall()
    return filas[0][0] if filas else None


def _insertar(con, sql, params) -> int:
    con.execute(sql, params)
    return _uno(con, "SELECT last_insert_rowid()")


def _observar(con, plan_id, tipo, detalle):
    con.execute("INSERT INTO observacion_plan (plan_id, tipo, detalle) VALUES (?, ?, ?)", (plan_id, tipo, detalle))


def cargar_carpeta(con, carpeta: Path = CARPETA) -> list[int]:
    """Carga todos los planes de `carpeta` que aún no existan. → ids de los planes creados."""
    creados = []
    with open(carpeta / "planes.csv", encoding="utf-8", newline="") as f:
        planes = list(csv.DictReader(f))
    conocidas = []
    if (carpeta / "observaciones.csv").exists():
        with open(carpeta / "observaciones.csv", encoding="utf-8", newline="") as f:
            conocidas = list(csv.DictReader(f))
    for p in planes:
        with open(carpeta / p["archivo"], encoding="utf-8", newline="") as f:
            filas = list(csv.DictReader(f))
        pid = cargar_plan(con, p, filas, [o for o in conocidas if o["archivo"] == p["archivo"]])
        if pid:
            creados.append(pid)
    return creados


def cargar_plan(con, p: dict, filas: list[dict], conocidas: list[dict] = ()) -> int | None:
    unidad = _uno(con, "SELECT id FROM unidad WHERE sigla = 'CMAT'")
    programa = _uno(con, "SELECT id FROM programa WHERE nombre = ?", (p["programa"],)) or _insertar(
        con, "INSERT INTO programa (nombre, nivel, unidad_id) VALUES (?, ?, ?)", (p["programa"], p["nivel"], unidad))
    if _uno(con, "SELECT id FROM plan_estudios WHERE programa_id = ? AND nombre = ?", (programa, p["plan"])):
        return None
    plan = _insertar(con, """INSERT INTO plan_estudios (programa_id, nombre, resolucion, vigente_desde, sistema,
                             semanas_semestre, horas_por_credito, nota_minima, total_teoricas, total_practicas,
                             total_laboratorio, total_creditos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (programa, p["plan"], p["resolucion"] or None, int(p["vigente_desde"]), p["sistema"],
                      _entero(p["semanas_semestre"]), _entero(p["horas_por_credito"]), _entero(p["nota_minima"]),
                      _entero(p["total_teoricas"]), _entero(p["total_practicas"]), _entero(p["total_laboratorio"]),
                      _entero(p["total_creditos"])))
    vistas = {}
    for orden, f in enumerate(filas):
        sigla = f["sigla"].strip()
        asignatura = None
        if sigla:
            nombre = f["nombre"].strip()
            fila = con.execute("SELECT id, nombre FROM asignatura WHERE sigla = ?", (sigla,)).fetchall()
            if fila:
                asignatura = fila[0][0]
                if fila[0][1] != nombre:
                    _observar(con, plan, "nombre", f"{sigla}: el plan la llama «{nombre}»; en el catálogo es "
                                                   f"«{fila[0][1]}» (se conserva este).")
            else:
                depto = sigla.split("-")[0]
                asignatura = _insertar(con, """INSERT INTO asignatura (sigla, nombre, departamento, de_la_carrera)
                                               VALUES (?, ?, ?, ?)""",
                                       (sigla, nombre, depto, int(depto == DEPARTAMENTO_PROPIO)))
            if sigla in vistas:
                _observar(con, plan, "duplicada", f"{sigla} figura dos veces en el plan (requisitos: "
                                                  f"{vistas[sigla] or '—'} y {f['requisitos'] or '—'}); se "
                                                  "carga la primera.")
                continue
            vistas[sigla] = f["requisitos"]
        pa = _insertar(con, """INSERT INTO plan_asignatura (plan_id, asignatura_id, tipo, semestre, ciclo, horas_teoricas,
                               horas_practicas, horas_laboratorio, creditos, orden) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (plan, asignatura, f["tipo"], _entero(f["semestre"]), f["ciclo"] or None,
                        _entero(f["horas_teoricas"]), _entero(f["horas_practicas"]), _entero(f["horas_laboratorio"]),
                        _entero(f["creditos"]), orden))
        for r in (x.strip() for x in (f["requisitos"] or "").split(";") if x.strip()):
            if r.lower() == "egresado":
                con.execute("INSERT INTO requisito (plan_asignatura_id, condicion) VALUES (?, 'egresado')", (pa,))
            else:
                con.execute("INSERT INTO requisito (plan_asignatura_id, sigla) VALUES (?, ?)", (pa, r))
    for o in conocidas:
        _observar(con, plan, "documento", f"{o['sigla']}: {o['detalle']}" if o["sigla"] else o["detalle"])
    validar(con, plan)
    return plan


def validar(con, plan: int):
    """Registra lo que no cuadra: requisitos inexistentes y totales distintos de los declarados."""
    siglas = {s for (s,) in con.execute("""SELECT a.sigla FROM plan_asignatura pa JOIN asignatura a
                                           ON a.id = pa.asignatura_id WHERE pa.plan_id = ?""", (plan,)).fetchall()}
    for sigla, requiere in con.execute(
            """SELECT a.sigla, r.sigla FROM requisito r JOIN plan_asignatura pa ON pa.id = r.plan_asignatura_id
               JOIN asignatura a ON a.id = pa.asignatura_id WHERE pa.plan_id = ? AND r.sigla IS NOT NULL
               ORDER BY pa.orden""", (plan,)).fetchall():
        if requiere not in siglas:
            _observar(con, plan, "requisito", f"{sigla}: su requisito {requiere} no figura en el plan.")
    for total, (declarado, calculado) in totales(con, plan).items():
        if declarado is not None and calculado != declarado:
            _observar(con, plan, "totales", f"Total de horas {total}: el documento declara {declarado:,}; la suma de "
                                            f"las asignaturas y casillas del plan da {calculado:,}.".replace(",", "."))


def totales(con, plan: int) -> dict:
    """{'teóricas': (declarado, calculado), …}. Horas: suma de las horas semanales de las asignaturas
    ubicadas en un semestre (y las casillas de electiva) × semanas del semestre. Créditos: suma."""
    p = con.execute("""SELECT sistema, semanas_semestre, total_teoricas, total_practicas, total_laboratorio,
                              total_creditos FROM plan_estudios WHERE id = ?""", (plan,)).fetchall()[0]
    sistema, semanas, tt, tp, tl, tc = p
    suma = con.execute("""SELECT COALESCE(SUM(horas_teoricas), 0), COALESCE(SUM(horas_practicas), 0),
                                 COALESCE(SUM(horas_laboratorio), 0), COALESCE(SUM(creditos), 0)
                          FROM plan_asignatura WHERE plan_id = ? AND semestre IS NOT NULL""", (plan,)).fetchall()[0]
    if sistema == "horas":
        s = semanas or 0
        return {"teóricas": (tt, suma[0] * s), "prácticas": (tp, suma[1] * s), "de laboratorio": (tl, suma[2] * s)}
    return {"en créditos": (tc, suma[3])}
