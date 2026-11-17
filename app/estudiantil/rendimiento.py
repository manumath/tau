"""Vacantes de admisión y rendimiento por asignatura (PLAN §72, etapa 7; acciones A4.4 y A4.5 del plan de mejora).

- **Vacantes:** la Dirección de Carrera registra por admisión (semestre I o II) las vacantes ofertadas y los postulantes;
  los **admitidos no se escriben**: son los ingresantes de esa cohorte en el CSV de Seguimiento Académico.
- **Rendimiento:** agregados del Sistema de Seguimiento Académico por asignatura y gestión (inscritos, aprobados,
  reprobados, abandonos), **sin RU, nombres ni notas** (decisión del usuario del 14-nov-2026). Una asignatura con menos de
  `MIN_CELDA` inscritos se muestra como «menos de 5» y **no entra** en los totales por línea formativa ni de la gestión:
  así no se puede deducir por resta.
"""
import csv
import io

from app.comun.db import get_db, sin_tildes, transaccion
from app.comun.importar_usuarios import MAX_BYTES, leer_tabla  # noqa: F401  (MAX_BYTES lo usa la ruta)
from app.estudiantil import cohortes

MIN_CELDA = 5
CICLOS_ADMISION = ("I", "II")
CICLOS = ("I", "II", "INV", "VER")
MAX_FILAS = 3000
ALIAS = {"sigla": ("sigla", "codigo", "asignatura"), "gestion": ("gestion", "periodo", "semestre"),
         "inscritos": ("inscritos",), "aprobados": ("aprobados",), "reprobados": ("reprobados",),
         "abandonos": ("abandonos", "abandono", "retirados", "no se presento")}
PLANTILLA = "sigla,gestion,inscritos,aprobados,reprobados,abandonos\nMAT-111,I-2025,62,30,21,11\nMAT-112,I-2025,4,3,1,0\n"


# --- Vacantes ---------------------------------------------------------------------------------------------------------------

def vacantes() -> list[dict]:
    """Cada admisión registrada, la más reciente primero, con sus admitidos (de las cohortes) y sus tasas."""
    alumnos = cohortes.alumnos()
    filas = get_db().q("SELECT * FROM vacante_admision ORDER BY anio DESC, ciclo DESC")
    for f in filas:
        o = cohortes.ordinal(f["anio"], f["ciclo"])
        # Sin estudiantes de esa cohorte, la cohorte no está cargada: no es «0 admitidos» (ensayo del piloto, etapa 11).
        f["admitidos"] = sum(e["ingreso"] == o for e in alumnos) or None
        f["cobertura"] = round(100 * f["admitidos"] / f["vacantes"], 1) if f["vacantes"] and f["admitidos"] else None
        f["postulantes_por_vacante"] = round(f["postulantes"] / f["vacantes"], 2) \
            if f["vacantes"] and f["postulantes"] is not None else None
    return filas


def vacantes_de(anio: int, ciclo: str) -> dict | None:
    return next((f for f in vacantes() if f["anio"] == anio and f["ciclo"] == ciclo), None)


def _entero(texto, nombre, errores, obligatorio=False):
    t = str(texto or "").strip().replace(".", "")
    if not t:
        if obligatorio:
            errores.append(f"Indique {nombre}.")
        return None
    if not t.isdigit():
        errores.append(f"Escriba {nombre} como número entero.")
        return None
    return int(t)


def guardar_vacantes(d: dict, uid: int) -> tuple[dict, list[str]]:
    """Registra o corrige (misma admisión) las vacantes y los postulantes."""
    errores: list[str] = []
    anio = _entero(d.get("anio"), "el año", errores, obligatorio=True)
    ciclo = d.get("ciclo") or ""
    if ciclo not in CICLOS_ADMISION:
        errores.append("Elija el semestre de la admisión (I o II).")
    x = {"anio": anio, "ciclo": ciclo, "vacantes": _entero(d.get("vacantes"), "las vacantes", errores, obligatorio=True),
         "postulantes": _entero(d.get("postulantes"), "los postulantes", errores),
         "nota": (d.get("nota") or "").strip()[:500] or None}
    if anio is not None and not 1990 <= anio <= 2100:
        errores.append("El año no es válido.")
    if errores:
        return x, errores
    db = get_db()
    previa = db.q("SELECT id FROM vacante_admision WHERE anio = ? AND ciclo = ?", [anio, ciclo])
    if previa:
        db.t.vacante_admision.update({**x, "registrado_por": uid}, previa[0]["id"])
    else:
        db.t.vacante_admision.insert(**x, registrado_por=uid)
    return x, []


def eliminar_vacantes(vid: int) -> bool:
    if not get_db().q("SELECT 1 FROM vacante_admision WHERE id = ?", [vid]):
        return False
    get_db().t.vacante_admision.delete(vid)
    return True


def indicadores_vacantes(anio: int) -> dict | None:
    """Cifras del año (admisiones I y II con vacantes registradas): cobertura y postulantes por vacante."""
    filas = [f for f in vacantes() if f["anio"] == anio]
    if not filas:
        return None
    v = sum(f["vacantes"] for f in filas)
    con_post = [f for f in filas if f["postulantes"] is not None]
    con_cohorte = [f for f in filas if f["admitidos"] is not None]     # la cobertura, solo con la cohorte cargada
    return {"vacantes": sum(f["vacantes"] for f in con_cohorte), "admitidos": sum(f["admitidos"] for f in con_cohorte),
            "vacantes_registradas": v,
            "postulantes": sum(f["postulantes"] for f in con_post) if con_post else None,
            "vacantes_con_postulantes": sum(f["vacantes"] for f in con_post)}


# --- Rendimiento ------------------------------------------------------------------------------------------------------------

def _gestion(texto: str) -> tuple[int, str] | None:
    """«I-2025», «II/2025», «2025-I», «VER-2025» → (2025, 'I')."""
    t = (texto or "").strip().upper().replace("/", "-").replace(" ", "-")
    partes = [p for p in t.split("-") if p]
    if len(partes) != 2:
        return None
    a, b = partes
    ciclo, anio = (a, b) if b.isdigit() else (b, a)
    if ciclo not in CICLOS or not anio.isdigit() or not 1990 <= int(anio) <= 2100:
        return None
    return int(anio), ciclo


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (filas, errores generales). Cada fila: linea, sigla, gestion, datos, estado ('nueva' | 'reemplaza' | 'error'),
    mensaje. Una sigla que no está en el catálogo de asignaturas es un error (el catálogo es común a los planes)."""
    filas, errores = leer_tabla(contenido, ALIAS, tuple(ALIAS), MAX_FILAS)
    if errores:
        return [], errores
    siglas = {sin_tildes(f["sigla"]).upper(): f["id"] for f in get_db().q("SELECT id, sigla FROM asignatura")}
    existentes = {(f["asignatura_id"], f["anio"], f["ciclo"])
                  for f in get_db().q("SELECT asignatura_id, anio, ciclo FROM rendimiento_asignatura")}
    vistas, salida = set(), []
    for linea, d in filas:
        msg = []
        aid = siglas.get(sin_tildes(d["sigla"]).upper().replace(" ", "-"))
        if not aid:
            msg.append(f"La sigla «{d['sigla']}» no está en el catálogo de asignaturas.")
        g = _gestion(d["gestion"])
        if not g:
            msg.append(f"Gestión «{d['gestion']}» no válida: escriba, por ejemplo, I-2025.")
        nums = {}
        for k in ("inscritos", "aprobados", "reprobados", "abandonos"):
            n = _entero(d[k], k, msg, obligatorio=True)
            nums[k] = n
        if not msg and nums["aprobados"] + nums["reprobados"] + nums["abandonos"] > nums["inscritos"]:
            msg.append("Aprobados, reprobados y abandonos suman más que los inscritos.")
        clave = (aid, *g) if aid and g else None
        if clave and clave in vistas:
            msg.append("La asignatura y la gestión se repiten en el archivo.")
        if clave:
            vistas.add(clave)
        estado = "error" if msg else ("reemplaza" if clave in existentes else "nueva")
        salida.append({"linea": linea, "sigla": d["sigla"], "gestion": d["gestion"], "estado": estado,
                       "mensaje": " ".join(msg), "datos": None if msg else {"asignatura_id": aid, "anio": g[0],
                                                                              "ciclo": g[1], **nums}})
    return salida, []


def aplicar(filas: list[dict], uid: int) -> int:
    n = 0
    with transaccion():
        for f in filas:
            if f["estado"] == "error":
                continue
            x = f["datos"]
            get_db().conn.execute("DELETE FROM rendimiento_asignatura WHERE asignatura_id = ? AND anio = ? AND ciclo = ?",
                                  [x["asignatura_id"], x["anio"], x["ciclo"]])
            get_db().t.rendimiento_asignatura.insert(**x, cargado_por=uid)
            n += 1
    return n


def gestiones() -> list[tuple[int, str]]:
    orden = {c: i for i, c in enumerate(("VER", "II", "INV", "I"))}
    filas = get_db().q("SELECT DISTINCT anio, ciclo FROM rendimiento_asignatura")
    return sorted(((f["anio"], f["ciclo"]) for f in filas), key=lambda g: (-g[0], orden[g[1]]))


def _tasas(x: dict) -> dict:
    i = x["inscritos"]
    return {**x, "aprobacion": round(100 * x["aprobados"] / i, 1) if i else None,
            "abandono": round(100 * x["abandonos"] / i, 1) if i else None}


def por_asignatura(anio: int, ciclo: str) -> list[dict]:
    """Filas de la gestión. Las de menos de `MIN_CELDA` inscritos salen con `oculta` y sin cifras."""
    filas = get_db().q(
        """SELECT r.*, a.sigla, a.nombre, COALESCE(a.linea_formativa, '') AS linea FROM rendimiento_asignatura r
           JOIN asignatura a ON a.id = r.asignatura_id WHERE r.anio = ? AND r.ciclo = ? ORDER BY a.sigla""", [anio, ciclo])
    salida = []
    for f in filas:
        if f["inscritos"] < MIN_CELDA:
            salida.append({"sigla": f["sigla"], "nombre": f["nombre"], "linea": f["linea"], "oculta": True})
        else:
            salida.append({**_tasas(f), "oculta": False})
    return salida


def por_linea(filas: list[dict]) -> list[dict]:
    """Totales por línea formativa y de la gestión, solo con las asignaturas que se muestran."""
    grupos: dict[str, dict] = {}
    for f in filas:
        if f["oculta"]:
            continue
        g = grupos.setdefault(f["linea"] or "Sin línea formativa", {"linea": f["linea"] or "Sin línea formativa",
                                                                    "asignaturas": 0, "inscritos": 0, "aprobados": 0,
                                                                    "reprobados": 0, "abandonos": 0})
        g["asignaturas"] += 1
        for k in ("inscritos", "aprobados", "reprobados", "abandonos"):
            g[k] += f[k]
    lineas = [_tasas(g) for g in sorted(grupos.values(), key=lambda g: g["linea"])]
    if lineas:
        total = {"linea": "Total de la gestión", "asignaturas": sum(g["asignaturas"] for g in lineas),
                 **{k: sum(g[k] for g in lineas) for k in ("inscritos", "aprobados", "reprobados", "abandonos")}}
        lineas.append(_tasas(total))
    return lineas


def a_csv(anio: int, ciclo: str) -> str:
    """Exportación de la gestión con la misma regla del mínimo (las ocultas van sin cifras)."""
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["sigla", "asignatura", "linea_formativa", "inscritos", "aprobados", "reprobados", "abandonos",
                "aprobacion_pct", "abandono_pct"])
    for f in por_asignatura(anio, ciclo):
        if f["oculta"]:
            w.writerow([f["sigla"], f["nombre"], f["linea"], f"menos de {MIN_CELDA}", "", "", "", "", ""])
        else:
            w.writerow([f["sigla"], f["nombre"], f["linea"], f["inscritos"], f["aprobados"], f["reprobados"],
                        f["abandonos"], f["aprobacion"], f["abandono"]])
    return salida.getvalue()
