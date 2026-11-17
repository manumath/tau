"""Lo que los módulos de docencia aportan al menú, la búsqueda y el inicio (PLAN §73, etapa 2)."""
from datetime import date, timedelta

from app.academico import carga, gestiones, preparacion, semestre as ciclo_semestre
from app.academico.componentes import PESTANAS, es_docente, tiene_docencia, visible
from app.comun import formato, permisos, vinculos
from app.comun.componentes.bandeja import nombres, plural
from app.comun.db import get_db, patron_busqueda
from app.comun.menu import agenda_en_el_menu, item

ICONOS = {"mia": "presentation", "pendientes": "list-checks", "calendario": "calendar-days", "historial": "history",
          "listas": "users", "evaluacion": "clipboard-check", "programas": "notebook-text", "preferencias": "list-filter",
          "preferencias_todas": "users-round", "preparacion": "calendar-check", "planes": "book-marked",
          "oferta": "layout-list", "carga": "clock", "gestiones": "calendar-range"}
# Pestaña de Docencia → módulo dueño; las que no están aquí son de `oferta`.
DE_OTRO_MODULO = {"planes": "planes", "evaluacion": "evaluacion_docente"}


def _menu(modulo):
    """Los ítems de Docencia de ese módulo, en el orden de PESTANAS (app/academico/componentes.py)."""
    def aporte(auth):
        return [("Docencia", 10 * n, item(c, t, u, ICONOS[c])) for n, (c, t, u, cond) in enumerate(PESTANAS)
                if DE_OTRO_MODULO.get(c, "oferta") == modulo and visible(cond, auth)]
    return aporte


menu_planes, _menu_docencia, menu_evaluacion = _menu("planes"), _menu("oferta"), _menu("evaluacion_docente")


def menu_oferta(auth):
    """Las pestañas de Docencia y, para quien es docente, sus pendientes y su calendario (los de toda la persona)."""
    return (agenda_en_el_menu() if es_docente(auth) else []) + _menu_docencia(auth)


def portal_evaluacion(auth):
    """En el portal del estudiante (el módulo de evaluación docente se declara en este paquete)."""
    return [("Servicios", 20, item("evaluacion", "Evaluación docente", "/estudiante/evaluacion", "clipboard-check"))]


def _asignaturas(q, auth, limite):
    """Llevan a la fila de la asignatura en el plan más reciente que la incluye."""
    filas = get_db().q(
        """SELECT a.sigla, a.nombre, MAX(pa.plan_id) AS plan_id FROM asignatura a
           JOIN plan_asignatura pa ON pa.asignatura_id = a.id
           JOIN plan_estudios pl ON pl.id = pa.plan_id AND pl.estado <> 'elaboracion'
           WHERE a.sigla LIKE :p OR sin_tildes(a.nombre) LIKE :p
           GROUP BY a.id ORDER BY a.sigla LIMIT :l""", {"p": patron_busqueda(q), "l": limite})
    return [{"texto": f"{f['sigla']} · {f['nombre']}", "href": f"/docencia/planes/{f['plan_id']}#asignatura-{f['sigla']}",
             "detalle": "Plan de estudios"} for f in filas]


BUSQUEDA_PLANES = [(60, "Asignaturas", "graduation-cap", _asignaturas)]


# --- Inicio --------------------------------------------------------------------------------------------------------

def _carrera(auth):
    """Dirección de Carrera y Coordinación académica: el semestre y los vínculos."""
    dirige = permisos.puede(auth, "gestionar_vinculos", vinculos.carrera())
    if not (dirige or permisos.puede(auth, "gestionar_oferta")):
        return []
    g = carga.semestre_de_referencia()
    items = []
    if g:
        sin_docente = get_db().q(
            """SELECT COUNT(*) n FROM oferta o WHERE o.gestion_id = ? AND o.retirada_en IS NULL AND NOT EXISTS (
                   SELECT 1 FROM oferta_docente d WHERE d.oferta_id = o.id AND d.rol = 'titular'
                   AND d.hasta IS NULL)""", [g["id"]])[0]["n"]
        if sin_docente:
            items.append({"texto": f"{plural(sin_docente, 'materia')} sin docente titular en {gestiones.codigo(g)}",
                          "href": f"/docencia/oferta?gestion={g['id']}"})
        if dirige:
            revisar = [x for x in carga.personas(g) if x["avisos"]]
            if revisar:
                items.append({"texto": f"{plural(len(revisar), 'docente')} con la carga de {gestiones.codigo(g)} por revisar",
                              "href": f"/docencia/carga?gestion={g['id']}", "detalle": nombres(revisar)})
    hoy = date.today()
    for pl in get_db().q("""SELECT * FROM gestion_academica WHERE estado = 'planificacion' AND fecha_inicio <= ?
                            ORDER BY fecha_inicio""", [(hoy + timedelta(days=15)).isoformat()]):
        empezo = pl["fecha_inicio"] <= hoy.isoformat()
        falta = ciclo_semestre.bloqueos(pl)
        items.append({"texto": f"{gestiones.codigo(pl)} {'empezó el' if empezo else 'empieza el'} "
                               f"{formato.fecha(pl['fecha_inicio'])} y sigue en planificación",
                      "href": f"/docencia/preparacion?semestre={gestiones.codigo(pl)}", "tono": "rojo" if empezo else "info",
                      "detalle": (f"Para activarla: {falta[0].lower()}" if falta else "Está lista para activarse.")})
    for ac in get_db().q("SELECT * FROM gestion_academica WHERE estado = 'activa' AND fecha_fin < ? ORDER BY fecha_fin",
                         [hoy.isoformat()]):
        items.append({"texto": f"{gestiones.codigo(ac)} terminó el {formato.fecha(ac['fecha_fin'])} y sigue activa",
                      "href": f"/docencia/preparacion?semestre={gestiones.codigo(ac)}",
                      "detalle": "Al concluirlo pasa al historial." if dirige else "La concluye la Dirección de Carrera."})
    prox = preparacion.estado(*preparacion.semestre_siguiente())
    if prox["hechas"] < prox["total"]:
        falta = next(e for e in prox["etapas"] if not e["listo"])
        items.append({"texto": f"Preparación de {prox['codigo']}: {prox['hechas']} de {prox['total']} etapas listas",
                      "href": f"/docencia/preparacion?semestre={prox['codigo']}", "tono": "info",
                      "detalle": f"Siguiente: {falta['falta']}."})
    if dirige:
        vencen = carga.contratos_por_vencer(30)
        if vencen:
            items.append({"texto": f"{plural(len(vencen), 'vínculo')} termina{'n' if len(vencen) != 1 else ''} en los "
                                   "próximos 30 días sin un periodo nuevo registrado", "href": "/docencia/renovaciones",
                          "detalle": "; ".join(f"{f['nombres']} {f['apellidos']} ({f['fecha_fin']})" for f in vencen[:4])})
        sin_carga = carga.vigentes_sin_carga()
        if sin_carga:
            items.append({"texto": f"{plural(len(sin_carga), 'docente')} con vínculo vigente sin carga contratada",
                          "href": "/admin/usuarios", "detalle": nombres(sin_carga)})
    return items


def _mi_docencia(auth):
    if not tiene_docencia(auth):
        return []
    g = carga.semestre_de_referencia()
    if not g:
        return []
    r = carga.resumen(auth["id"], g)
    n = len(carga.materias_con_detalle(auth["id"], g["id"]))
    return [{"texto": f"{gestiones.codigo(g)}: {plural(n, 'materia')}"
                      + (f" · {r['contratada']} h/mes contratadas" if r["contratada"] else ""),
             "href": "/docencia/mia", "tono": "ambar" if r["avisos"] else "info",
             "detalle": r["avisos"][0] if r["avisos"] else None}]


def inicio_oferta(auth):
    return ([("mio", 50, x) for x in _mi_docencia(auth)]
            + [("carrera", 10 * n, x) for n, x in enumerate(_carrera(auth))])


# --- Lo que queda en curso al apagar un módulo (PLAN §73, etapa 3) ------------------------------------------------------

def en_curso_oferta():
    activas = [gestiones.codigo(g) for g in get_db().q("SELECT * FROM gestion_academica WHERE estado = 'activa'")]
    return [f"{len(activas)} semestre(s) activo(s): {', '.join(activas)}"] if activas else []


def en_curso_evaluacion():
    n = get_db().q("SELECT COUNT(*) n FROM evaluacion_docente WHERE estado IN ('anunciada', 'abierta')")[0]["n"]
    return [f"{n} evaluación(es) docente(s) anunciada(s) o abierta(s)"] if n else []
