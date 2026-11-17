"""Lo que los módulos de estudiantes aportan al menú y al inicio (PLAN §73, etapa 2)."""
from app.comun import estudiantes, permisos, vinculos
from app.comun.calendario import evento, pendiente
from app.comun.componentes.bandeja import nombres, plural
from app.comun.db import get_db
from app.comun.menu import item
from app.estudiantil import actividad, encuestas, tutoria

G = "Estudiantes"


def _seguimiento(auth) -> bool:
    return permisos.puede(auth, "ver_seguimiento_estudiantil")


def menu_estudiantes(auth):
    return [(G, 10, item("cohortes", "Cohortes estudiantiles", "/docencia/cohortes", "users-round"))] if _seguimiento(auth) else []


def menu_encuestas(auth):
    return [(G, 20, item("encuestas", "Encuestas", "/docencia/encuestas", "clipboard-list"))] if _seguimiento(auth) else []


def menu_tutoria(auth):
    items = []
    if auth.get("es_tutor"):
        items.append((G, 0, item("mis-tutorados", "Mis tutorados", "/tutoria", "message-circle-heart")))
    if _seguimiento(auth):
        items.append((G, 30, item("tutoria", "Tutoría", "/docencia/tutoria", "message-circle")))
    if auth.get("es_tutor") or permisos.puede(auth, "gestionar_apoyo"):
        items.append((G, 60, item("apoyo-estudiantil", "Apoyo estudiantil", "/apoyo", "life-buoy")))
    if permisos.puede(auth, "gestionar_buzon"):
        items.append(("Servicios", 30, item("buzon", "Buzón de consultas", "/servicios/buzon", "inbox")))
    return items


# El portal del estudiante, en grupos (PLAN §67): cada servicio nuevo se agrega al aporte de su módulo.
C, S = "Mi carrera", "Servicios"


def portal_estudiantes(auth):
    return [(None, 0, item("estudiante", "Mi seguimiento", "/estudiante", "graduation-cap")),
            (C, 10, item("plan", "Mi plan de estudios", "/estudiante/plan", "book-marked")),
            (C, 20, item("calendario", "Calendario", "/estudiante/calendario", "calendar-days"))]


def portal_tutoria(auth):
    return [(C, 30, item("tutoria", "Mi tutoría", "/estudiante/tutoria", "message-circle-heart")),
            (C, 40, item("apoyo", "Apoyo", "/estudiante/apoyo", "life-buoy")),
            (C, 60, item("orientacion", "Orientación", "/estudiante/orientacion", "compass")),
            (C, 70, item("buzon", "Buzón", "/estudiante/buzon", "mail"))]


def portal_encuestas(auth):
    return [(S, 60, item("encuestas", "Encuestas", "/estudiante/encuestas", "clipboard-list"))]


# --- Inicio --------------------------------------------------------------------------------------------------------

def inicio_tutoria(auth):
    """El tutor: tutorados sin reuniones."""
    if not estudiantes.es_tutor(auth["id"]):
        return []
    sin = [t for t in tutoria.tutorados(auth["id"]) if not t["reuniones"]]
    return [("estudiantes", 10, {"texto": f"{plural(len(sin), 'tutorado')} sin reuniones registradas", "href": "/tutoria",
                                 "detalle": nombres(sin)})] if sin else []


def inicio_estudiantes(auth):
    """La Dirección de Carrera y la Coordinación: actividad estudiantil por verificar."""
    if not permisos.puede(auth, "verificar_actividad", vinculos.carrera()):
        return []
    n = actividad.n_pendientes()
    return [("estudiantes", 20, {"texto": f"{plural(n, 'actividad estudiantil', 'actividades estudiantiles')} por verificar",
                                 "href": "/docencia/cohortes/actividades"})] if n else []


# --- Pendientes y fechas (PLAN §73, etapa 3) -------------------------------------------------------------------------

def pendientes_tutoria(ambito, uid, hoy):
    if ambito != "docente":
        return []
    return [pendiente("tutoria", f"Reunión que pide {s['nombres']} {s['apellidos']}", (s["mensaje"] or "")[:120], None,
                      f"/tutoria/{s['externo_id']}")
            for s in tutoria.solicitudes_abiertas_de_tutor(uid) if s["estado"] == "pendiente"]


def eventos_tutoria(ambito, quien, desde, hasta):
    if ambito == "docente":
        return [evento(s["fecha_reunion"], f"Reunión con {s['nombres']} {s['apellidos']}", "tutoria", s["respuesta"] or "",
                       f"/tutoria/{s['externo_id']}")
                for s in tutoria.solicitudes_abiertas_de_tutor(quien) if s["estado"] == "programada"]
    if ambito == "estudiante":
        return [evento(s["fecha_reunion"], "Reunión con su tutor(a)", "tutoria", s["respuesta"] or "", "/estudiante/tutoria")
                for s in get_db().q("SELECT * FROM tutoria_solicitud WHERE externo_id = ? AND estado = 'programada'", [quien])]
    return []


def eventos_encuestas(ambito, quien, desde, hasta):
    if ambito != "estudiante":
        return []
    return [evento(e["cierra_el"], f"Cierra la encuesta: {e['titulo']}", "encuesta", "", f"/encuesta/{e['token']}")
            for e in encuestas.por_responder(quien)]


# --- Lo que queda en curso al apagar un módulo -------------------------------------------------------------------------

def _contar(sql: str) -> int:
    return get_db().q(sql)[0]["n"]


def en_curso_encuestas():
    n = _contar("SELECT COUNT(*) n FROM encuesta WHERE estado = 'abierta'")
    return [f"{n} encuesta(s) abierta(s): sus enlaces dejarán de responder"] if n else []


def en_curso_tutoria():
    casos = _contar("SELECT COUNT(*) n FROM caso_apoyo WHERE estado IN ('abierto', 'en_seguimiento')")
    reuniones = _contar("SELECT COUNT(*) n FROM tutoria_solicitud WHERE estado IN ('pendiente', 'programada')")
    return ([f"{casos} caso(s) de apoyo abierto(s)"] if casos else []) + (
        [f"{reuniones} reunión(es) de tutoría pedida(s) o programada(s)"] if reuniones else [])


def historial_tutoria(uid):
    """Cuántos estudiantes tuteló, en «Mi historial docente» (solo cifras: lo que se habló en las reuniones es confidencial)."""
    f = get_db().q("SELECT COUNT(*) AS total, SUM(hasta IS NULL) AS vigentes FROM tutoria_asignacion WHERE tutor_id = ?", [uid])[0]
    datos = {"total": f["total"] or 0, "vigentes": f["vigentes"] or 0}
    return [{"clave": "tutorados", "orden": 50, "titulo": "Tutoría de estudiantes", "datos": datos,
             "nota": f"{datos['total']} estudiante(s) tutelados en total, {datos['vigentes']} vigentes. Lo que se habló en las "
                     "reuniones es confidencial y no aparece aquí."}]

