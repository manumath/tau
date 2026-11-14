"""Datos de los formularios imprimibles del reglamento de 2023 (PLAN §70, etapa 6): 1 (habilitación), 2-1, 2-2 y 2-3 (méritos), 3 (sorteo
del tema), 4 (examen oral) y 5 (acta final). Aquí solo se reúnen y promedian los datos; la presentación está en `rutas/formularios.py`.

Como cada miembro del tribunal califica por su cuenta (decisión 4 del 7-nov-2026), el acta de cada postulante muestra el **promedio** de lo
que anotaron los miembros, línea por línea, que es la nota que entra al resultado; las firmas de la comisión las pone el papel."""
from statistics import mean

from app.comun.db import get_db
from app.servicios import auxiliaturas as aux
from app.servicios import rubricas

FORMULARIOS = {"1": "Formulario de habilitación", "2": "Acta de calificación de méritos", "3": "Sorteo del tema del examen oral",
               "4": "Acta del examen oral", "5": "Acta final del concurso"}


def _por_miembro(pid: int, fase: str) -> dict[int, dict[str, float]]:
    res: dict[int, dict[str, float]] = {}
    for f in get_db().q("SELECT miembro_id, clave, cantidad FROM calificacion_detalle WHERE postulacion_id = ? AND fase = ?", [pid, fase]):
        res.setdefault(f["miembro_id"], {})[f["clave"]] = f["cantidad"]
    return res


def acta_meritos(c: dict, pid: int) -> dict | None:
    """El formulario 2-1, 2-2 o 2-3 de un postulante con el promedio de los miembros: cada sección con sus líneas (cantidad media) y su
    puntaje, y el total. None si ningún miembro lo calificó."""
    miembros = _por_miembro(pid, "meritos")
    if not miembros:
        return None
    resultados = [rubricas.calcular_meritos(c["modalidad"], d) for d in miembros.values()]
    secciones = []
    for i, s in enumerate(rubricas.secciones(c["modalidad"])):
        if s["numero"] == rubricas.SECCION_MATERIA:
            lineas = [(rubricas.SECCION_MATERIA, "Nota obtenida en la materia que postula", None, "nota",
                       mean(d.get(rubricas.SECCION_MATERIA, 0) for d in miembros.values()))]
        else:
            lineas = [(clave, texto, puntos, unidad, mean(d.get(clave, 0) for d in miembros.values())) for clave, texto, puntos, unidad in s["lineas"]]
        secciones.append({"numero": s["numero"], "titulo": s["titulo"], "maximo": s["maximo"], "lineas": lineas,
                          "puntos": mean(r["secciones"][i]["puntos"] for r in resultados)})
    return {"miembros": len(miembros), "secciones": secciones, "total": mean(r["total"] for r in resultados)}


def acta_oral(pid: int) -> dict | None:
    """El formulario 4 de un postulante: promedio de cada criterio de la rúbrica y el total."""
    miembros = _por_miembro(pid, "oral")
    if not miembros:
        return None
    return {"miembros": len(miembros), "criterios": [(clave, texto, maximo, mean(d.get(clave, 0) for d in miembros.values()))
                                                     for clave, texto, maximo in rubricas.ORAL],
            "total": mean(rubricas.calcular_oral(d) for d in miembros.values())}


def habilitacion(it: dict) -> list[dict]:
    """El formulario 1: por cada postulante, qué requisitos cumple, el plan de trabajo y el resultado de la habilitación."""
    cerrada = bool(aux.cierre_de(it["id"], "habilitacion"))
    filas = []
    for p in aux.en_concurso(it["id"]):
        post = aux.postulacion(p["id"])
        nota = aux.nota(p["id"], "habilitacion")
        resultado = None
        if p["estado"] == "no_habilitada":
            resultado = False
        elif cerrada and nota is not None:
            resultado = nota > 0.5
        filas.append({**p, "requisitos": [(r["texto"], r["cumplido"], r["opcional"]) for r in aux.requisitos_de(post)],
                      "plan": bool((p["propuesta"] or "").strip()), "habilitado": resultado})
    return filas


def final(it: dict) -> list[dict]:
    """El formulario 5: notas de méritos, escrito y oral y el total de los postulantes habilitados."""
    res = []
    for p in aux.en_concurso(it["id"]):
        if p["estado"] == "no_habilitada":
            continue
        notas = {f: aux.nota(p["id"], f) for f in ("meritos", "escrito", "oral")}
        res.append({**p, "notas": notas, "total": round(sum(v or 0 for v in notas.values()), 2)})
    return sorted(res, key=lambda r: (-r["total"], r["apellidos"], r["nombres"]))
