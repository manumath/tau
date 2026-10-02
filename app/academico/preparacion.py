"""Preparación de un semestre (I o II) para la Dirección de Carrera y la Coordinación académica: qué
etapas están listas y qué falta, con las mismas reglas que las pantallas donde se resuelve cada una.

Etapas: gestión creada → oferta cargada → contratos renovados → docentes asignados → carga cuadrada.
No son estrictamente sucesivas (se puede asignar docentes mientras se renuevan contratos), pero
sin gestión no hay oferta y sin oferta no hay docentes ni carga que revisar.
"""
from datetime import date

from app.academico import carga, gestiones, oferta
from app.comun.db import get_db


def semestre_siguiente(hoy: date | None = None) -> tuple[int, str]:
    """El próximo semestre (I o II) que aún no empezó, exista o no su gestión."""
    hoy = hoy or date.today()
    for anio in (hoy.year, hoy.year + 1):
        for tipo in carga.SEMESTRES:
            g = gestiones.por_codigo(f"{tipo}-{anio}")
            inicio = g["fecha_inicio"] if g else gestiones.fechas_por_omision(anio, tipo)[0]
            if inicio > hoy.isoformat():
                return anio, tipo
    return hoy.year + 1, "I"


def semestres_elegibles(hoy: date | None = None) -> list[tuple[int, str]]:
    """El próximo semestre y los ya creados (para el selector), del más reciente al más antiguo."""
    creados = {(g["anio"], g["tipo"]) for g in gestiones.listar() if g["tipo"] in carga.SEMESTRES}
    return sorted(creados | {semestre_siguiente(hoy)}, key=lambda x: (x[0], x[1] == "II"), reverse=True)


def _sin_docente(gid: int) -> list[dict]:
    return get_db().q(
        """SELECT o.id, o.paralelo, a.sigla, a.nombre FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id
           WHERE o.gestion_id = ? AND NOT EXISTS (SELECT 1 FROM oferta_docente d WHERE d.oferta_id = o.id
                                                   AND d.rol = 'titular')
           ORDER BY a.sigla, o.paralelo""", [gid])


def estado(anio: int, tipo: str) -> dict:
    """Etapas de la preparación del semestre, con sus cifras y lo pendiente de cada una.

    Cada etapa: clave, titulo, estado (hecho | actual | pendiente), detalle, falta (qué hacer, en una
    frase), href, hechos y total (para la barra de avance, si aplica) y pendientes (para listarlos)."""
    codigo = f"{tipo}-{anio}"
    g = gestiones.por_codigo(codigo)
    etapas = []

    def etapa(clave, titulo, listo, detalle, href, falta="", hechos=None, total=None, pendientes=(), bloqueada=False):
        etapas.append({"clave": clave, "titulo": titulo, "listo": listo, "bloqueada": bloqueada, "detalle": detalle,
                       "falta": falta, "href": href, "hechos": hechos, "total": total, "pendientes": list(pendientes)})

    def n(cantidad, singular, plural):
        return f"{cantidad} {singular if cantidad == 1 else plural}"

    etapa("gestion", "Gestión creada", bool(g),
          f"Del {g['fecha_inicio']} al {g['fecha_fin']}" if g else f"Crear las gestiones de {anio}", "/docencia/gestiones",
          falta=f"crear las gestiones de {anio}")
    paralelos = oferta.listar(g["id"]) if g else []
    if g:
        ofertadas = {p["asignatura_id"] for p in paralelos}
        troncales = [a for a in oferta.troncales(anio) if a["id"] not in ofertadas]
        etapa("oferta", "Oferta cargada", bool(paralelos),
              f"{len(paralelos)} paralelos" + (f"; {len(troncales)} troncales no ofertadas" if troncales else "")
              if paralelos else "Sin materias ofertadas", f"/docencia/oferta?gestion={g['id']}",
              falta="cargar la oferta", pendientes=[f"{a['sigla']} {a['nombre']} (troncal no ofertada)" for a in troncales])
        renovar = carga.candidatos_renovacion(g)
        etapa("contratos", "Contratos renovados", not renovar,
              f"{len(renovar)} por renovar" if renovar else "Ninguno pendiente",
              f"/docencia/renovaciones?gestion={g['id']}",
              falta=f"renovar {n(len(renovar), 'contrato', 'contratos')}", pendientes=[f"{v['apellidos']}, {v['nombres']} (terminó el {v['fecha_fin']})" for v in renovar])
        sin = _sin_docente(g["id"])
        etapa("docentes", "Docentes asignados", bool(paralelos) and not sin,
              f"{len(paralelos) - len(sin)} de {len(paralelos)} paralelos con titular" if paralelos else "Sin oferta",
              f"/docencia/oferta/{g['id']}/grilla", hechos=len(paralelos) - len(sin), total=len(paralelos),
              falta=f"asignar titular a {n(len(sin), 'paralelo', 'paralelos')}",
              pendientes=[f"{x['sigla']} {x['nombre']}, paralelo {x['paralelo']}" for x in sin],
              bloqueada=not paralelos)
        personas = [p for p in carga.personas(g) if p["vinculo"] or p["materias"]]
        revisar = [p for p in personas if p["avisos"]]
        etapa("carga", "Carga cuadrada", bool(personas) and not revisar,
              f"{len(personas) - len(revisar)} de {len(personas)} docentes sin observaciones" if personas
              else "Nadie con vínculo ni materias", f"/docencia/carga?gestion={g['id']}",
              hechos=len(personas) - len(revisar), total=len(personas),
              falta=f"revisar la carga de {n(len(revisar), 'docente', 'docentes')}" if personas else "asignar docentes",
              pendientes=[f"{p['apellidos']}, {p['nombres']}: {' '.join(p['avisos'])}" for p in revisar],
              bloqueada=not paralelos)
    else:
        for clave, titulo in (("oferta", "Oferta cargada"), ("contratos", "Contratos renovados"),
                              ("docentes", "Docentes asignados"), ("carga", "Carga cuadrada")):
            etapa(clave, titulo, False, "Primero, la gestión", None, bloqueada=True)

    # Estado para el indicador: la primera etapa sin terminar que se puede trabajar es la actual.
    actual = next((e for e in etapas if not e["listo"] and not e["bloqueada"]), None)
    for e in etapas:
        e["estado"] = "hecho" if e["listo"] else "actual" if e is actual else "pendiente"
    hechas = sum(e["listo"] for e in etapas)
    return {"anio": anio, "tipo": tipo, "codigo": codigo, "gestion": g, "etapas": etapas, "hechas": hechas,
            "total": len(etapas), "empezado": bool(g and g["fecha_inicio"] <= date.today().isoformat())}
