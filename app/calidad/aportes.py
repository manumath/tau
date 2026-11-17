"""Lo que los módulos de calidad y plan de mejora aportan al menú y al inicio (PLAN §73, etapa 2)."""

from app.calidad import actividades_mejora, cortes_mejora, impacto, indicadores, mejora

from app.comun import permisos
from app.comun.componentes.bandeja import plural
from app.comun.menu import agenda_en_el_menu, item

G = "Calidad"


def menu_calidad(auth):
    puede = lambda accion: permisos.puede(auth, accion)  # noqa: E731
    items = []
    if puede("ver_marco_calidad"):
        items += [(G, 20, item("marco", "Marco de calidad", "/calidad/marco", "layers")),
                  (G, 30, item("indicadores", "Indicadores", "/calidad/indicadores", "gauge"))]
    if puede("ver_evidencias_calidad"):
        items.append((G, 40, item("evidencias", "Evidencias", "/calidad/evidencias", "folder-open")))
    if puede("ver_autoevaluacion"):
        items.append((G, 50, item("autoevaluacion", "Autoevaluación", "/calidad/autoevaluaciones", "clipboard-check")))
    if puede("ver_marco_calidad"):
        items += [(G, 60, item("ficha", "Ficha estadística", "/calidad/ficha", "table-2")),
                  (G, 70, item("capacitacion", "Capacitación", "/calidad/capacitacion", "school")),
                  (G, 80, item("convenios", "Convenios", "/calidad/convenios", "handshake"))]
    if puede("ver_marco_calidad") or impacto.tiene_proyectos(auth["id"]):
        items.append((G, 90, item("impacto", "Impacto social", "/calidad/impacto", "heart-handshake")))
    return items


def menu_mejora(auth):
    responsable = mejora.tiene_acciones(auth["id"])
    if not (permisos.puede(auth, "ver_plan_mejora") or responsable):
        return []
    return [*(agenda_en_el_menu() if responsable else []),      # su parte del plan está en «Mis pendientes»
            (G, 100, item("mejora", "Plan de mejora", "/calidad/mejora", "list-todo"))]


# --- Inicio --------------------------------------------------------------------------------------------------------

def inicio_mejora(auth):
    acts = actividades_mejora.de_responsable(auth["id"])
    if not acts:
        return []
    urgentes = sum(t["semaforo"] in ("vencida", "en_riesgo") for t in acts)
    return [("mio", 60, {"texto": f"{plural(len(acts), 'actividad', 'actividades')} del plan de mejora a su cargo"
                                  + (f" ({urgentes} vencida(s) o en riesgo)" if urgentes else ""),
                         "href": "/pendientes", "tono": "ambar" if urgentes else "info"})]


# --- Pendientes, fechas y tareas (PLAN §73, etapa 3) -----------------------------------------------------------------

def eventos_mejora(ambito, quien, desde, hasta):
    """Los plazos de las actividades del plan a cargo de la persona, en el calendario del docente y del investigador."""
    return cortes_mejora.eventos(quien, desde, hasta) if ambito in ("docente", "investigador") else []


def bloque_mejora(auth, volver):
    """«Mi parte del plan de mejora», sobre la lista de pendientes."""
    from app.calidad.rutas.actividades_mejora import mi_parte   # diferida: es una pantalla
    return mi_parte(auth, volver)


# Tareas periódicas: se nombran con su módulo de Python para que se busquen al correr y no al importar.
MANTENIMIENTO_CALIDAD = [lambda: indicadores.mantenimiento()]             # cifras «a hoy» de los indicadores
MANTENIMIENTO_MEJORA = [lambda: mejora.avisar_vencimientos(),              # acciones del plan por vencer o vencidas
                        lambda: cortes_mejora.avisar()]                    # actividades sin avance antes del corte
