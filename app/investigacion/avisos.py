"""Avisos del flujo de proyectos. Cada uno se registra en el centro de avisos de su destinatario y
se le envía por correo según su preferencia (app.comun.notificaciones). Nunca se avisa a quien hizo
la acción (no tiene sentido avisarse a uno mismo)."""
from app.comun import notificaciones, permisos
from app.comun.db import get_db, vigente_hasta


def _titulo(tipo: str, registro_id: int) -> str:
    tabla = "actividad" if tipo == "actividad" else "producto"
    filas = get_db().q(f"SELECT titulo FROM {tabla} WHERE id = ?", [registro_id])
    return filas[0]["titulo"] if filas else "(registro eliminado)"


def _usuario(uid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM usuario WHERE id = ?", [uid])
    return filas[0] if filas else None


def _persona(uid: int) -> str:
    u = _usuario(uid)
    return f"{u['nombres']} {u['apellidos']}" if u else "(persona eliminada)"


def _proyecto(pid: int) -> str:
    return get_db().q("SELECT nombre FROM proyecto WHERE id = ?", [pid])[0]["nombre"]


def _url_proyecto(pid: int, tab: str) -> str:
    return f"/proyectos/{pid}?tab={tab}"


def _responsables(pid: int) -> list[dict]:
    return get_db().q(
        f"""SELECT u.* FROM proyecto_participante pp JOIN usuario u ON u.id = pp.investigador_id
           WHERE pp.proyecto_id = ? AND pp.rol IN ('responsable', 'co_responsable')
             AND {vigente_hasta('pp.fecha_hasta')}""", [pid])


# --- Registros propuestos a proyectos ----------------------------------------------------------------

def nueva_propuesta(tipo: str, registro_id: int, pid: int, propuesto_por: int):
    """A los responsables vigentes del proyecto: hay algo por revisar."""
    proyecto, quien = _proyecto(pid), _persona(propuesto_por)
    que = f"{'la actividad' if tipo == 'actividad' else 'el producto'} «{_titulo(tipo, registro_id)}»"
    for r in _responsables(pid):
        if r["id"] == propuesto_por:
            continue
        notificaciones.avisar(
            r, f"Nueva propuesta en «{proyecto}»", f"{quien} propuso {que}.", _url_proyecto(pid, "pendientes"),
            f"{quien} propuso {que} para el proyecto «{proyecto}».\n\nPuede aprobarlo o rechazarlo en la pestaña "
            "«Pendientes» del proyecto:")


def revision(tipo: str, registro_id: int, pid: int, estado: str, revisor: int, comentario: str | None = None):
    """A quien propuso: su propuesta fue aprobada o rechazada (con el motivo)."""
    tabla = "actividad_proyecto" if tipo == "actividad" else "producto_proyecto"
    col = "actividad_id" if tipo == "actividad" else "producto_id"
    fila = get_db().q(f"SELECT propuesto_por FROM {tabla} WHERE {col} = ? AND proyecto_id = ?", [registro_id, pid])
    if not fila or fila[0]["propuesto_por"] == revisor:
        return
    u = _usuario(fila[0]["propuesto_por"])
    proyecto, titulo = _proyecto(pid), _titulo(tipo, registro_id)
    if estado == "aprobado":
        notificaciones.avisar(u, f"Aprobado en «{proyecto}»: {titulo}", "Su propuesta ya forma parte del proyecto.",
                              _url_proyecto(pid, "actividades" if tipo == "actividad" else "productos"),
                              f"Su propuesta «{titulo}» ya forma parte del proyecto «{proyecto}».")
    else:
        notificaciones.avisar(
            u, f"Propuesta rechazada en «{proyecto}»: {titulo}", f"Motivo: {comentario}", "/proyectos",
            f"Su propuesta «{titulo}» para el proyecto «{proyecto}» fue rechazada.\n\nMotivo: {comentario}\n\n"
            "Si corresponde, corrija el registro y guárdelo con la casilla del proyecto marcada para volver a "
            "proponerlo:")


# --- Propuestas institucionales ------------------------------------------------------------------

def _url_propuesta(prop_id: int) -> str:
    return f"/propuestas/{prop_id}"


def propuesta_enviada(prop: dict, reenvio: bool):
    """A la Dirección del Instituto: hay una propuesta institucional por decidir."""
    periodo = f"{prop['periodo']}–{prop['periodo'] + 1}"
    accion = "reenvió, con las condiciones atendidas," if reenvio else "presentó"
    tipo = "continuidad" if prop["modalidad"] == "continuidad" else "proyecto nuevo"
    for uid in dict.fromkeys(u["id"] for u in permisos.con_rol("direccion_instituto")):
        if uid == prop["proponente_id"]:
            continue
        notificaciones.avisar(
            _usuario(uid),
            f"{'Propuesta corregida' if reenvio else 'Nueva propuesta'} institucional: «{prop['nombre']}»",
            f"{prop['proponente']} {accion} la propuesta ({tipo}, {periodo}).", _url_propuesta(prop["id"]),
            f"{prop['proponente']} {accion} la propuesta «{prop['nombre']}» ({tipo}) para el periodo {periodo}.\n\n"
            "Puede revisarla y decidir en:")


def propuesta_decidida(prop: dict, admin_id: int):
    """Al proponente y a los responsables del proyecto: la decisión de la administración."""
    periodo = f"{prop['periodo']}–{prop['periodo'] + 1}"
    textos = {
        "aceptada": ("aceptada", f"El proyecto rige de octubre de {prop['periodo']} a septiembre de "
                                 f"{prop['periodo'] + 1}."),
        "condicional": ("aceptada con condiciones",
                        f"Condiciones: {prop['comentario']}\n\nCorrija la propuesta y vuelva a enviarla; el "
                        "proyecto queda en espera hasta entonces."),
        "rechazada": ("rechazada", f"Motivo: {prop['comentario']}"),
    }
    estado, detalle = textos[prop["estado"]]
    destinatarios = {u["id"]: u for u in _responsables(prop["proyecto_id"])}
    proponente = _usuario(prop["proponente_id"])
    if proponente:
        destinatarios[proponente["id"]] = proponente
    for u in destinatarios.values():
        if u["id"] == admin_id:
            continue
        notificaciones.avisar(u, f"Propuesta {estado}: «{prop['nombre']}»", detalle.split("\n\n")[0],
                              _url_propuesta(prop["id"]),
                              f"La propuesta «{prop['nombre']}» para el periodo {periodo} fue {estado}.\n\n{detalle}")


def recordatorio_continuidad(p: dict, periodo: int, cierre: str):
    """A los responsables de un proyecto institucional que termina: si no proponen continuidad,
    concluye el 30 de septiembre."""
    for u in _responsables(p["id"]):
        notificaciones.avisar(
            u, f"Continuidad de «{p['nombre']}»: la convocatoria cierra el {cierre}",
            f"El proyecto termina el {p['fecha_fin']}: proponga la continuidad antes del {cierre}.",
            _url_proyecto(p["id"], "resumen"),
            f"El proyecto institucional «{p['nombre']}» termina el {p['fecha_fin']}. Si quiere continuarlo en el "
            f"periodo {periodo}–{periodo + 1}, presente la propuesta de continuidad antes del {cierre}; si no, el "
            "proyecto concluye en esa fecha.")


# --- Carga horaria en proyectos ----------------------------------------------------------------------

def carga_desvinculado(pid: int, uid: int, horas: int, fin: str):
    """A los responsables: un participante con carga en el proyecto quedó sin vínculo."""
    proyecto, persona = _proyecto(pid), _persona(uid)
    for r in _responsables(pid):
        if r["id"] == uid:
            continue
        notificaciones.avisar(
            r, f"«{proyecto}»: {persona} quedó sin vínculo",
            f"Su vínculo terminó el {fin}; figura sin carga en el proyecto.", _url_proyecto(pid, "pendientes"),
            f"El vínculo de {persona} con la Carrera terminó el {fin}. Tenía {horas} h/mes asignadas en el proyecto "
            f"«{proyecto}». Puede seguir como participante, pero desde esa fecha figura sin carga horaria. Si vuelve "
            "a vincularse, usted decide si le asigna carga otra vez.")


def carga_nuevo_vinculo(pid: int, uid: int, libres: int, actividad: str):
    """A los responsables: un participante que tuvo carga en el proyecto volvió a vincularse."""
    proyecto, persona = _proyecto(pid), _persona(uid)
    texto_act = "investigación" if actividad == "investigacion" else "extensión"
    for r in _responsables(pid):
        if r["id"] == uid:
            continue
        notificaciones.avisar(
            r, f"«{proyecto}»: {persona} tiene un nuevo periodo de vínculo",
            f"Tiene {libres} h/mes de {texto_act} sin asignar; la carga no se reasigna sola.",
            _url_proyecto(pid, "participantes"),
            f"{persona}, que tuvo carga horaria en «{proyecto}», tiene un nuevo periodo de vínculo con {libres} h/mes "
            f"de {texto_act} sin asignar. La carga en el proyecto no se reasigna sola: si corresponde, asígnela en la "
            "pestaña «Participantes».")
