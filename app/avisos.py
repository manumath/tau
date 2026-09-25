"""Avisos por correo del flujo de proyectos. Respetan la preferencia `avisos_correo` y nunca
avisan a quien hizo la acción (no tiene sentido avisarse a uno mismo)."""
from app import config, correo
from app.db import get_db


def _titulo(tipo: str, registro_id: int) -> str:
    tabla = "actividad" if tipo == "actividad" else "producto"
    filas = get_db().q(f"SELECT titulo FROM {tabla} WHERE id = ?", [registro_id])
    return filas[0]["titulo"] if filas else "(registro eliminado)"


def _usuario(uid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM usuario WHERE id = ?", [uid])
    return filas[0] if filas else None


def _quiere(u: dict | None) -> bool:
    return bool(u and u["activo"] and u["avisos_correo"])


def _url_proyecto(pid: int, tab: str) -> str:
    return f"{config.URL_BASE}/proyectos/{pid}?tab={tab}"


def nueva_propuesta(tipo: str, registro_id: int, pid: int, propuesto_por: int):
    """A los responsables vigentes del proyecto: hay algo por revisar."""
    proyecto = get_db().q("SELECT nombre FROM proyecto WHERE id = ?", [pid])[0]["nombre"]
    quien = _usuario(propuesto_por)
    responsables = get_db().q(
        """SELECT u.* FROM proyecto_participante pp JOIN usuario u ON u.id = pp.investigador_id
           WHERE pp.proyecto_id = ? AND pp.rol IN ('responsable', 'co_responsable')
             AND (pp.fecha_hasta IS NULL OR pp.fecha_hasta >= date('now'))""", [pid])
    for r in responsables:
        if r["id"] == propuesto_por or not _quiere(r):
            continue
        correo.enviar(
            r["email"], f"Nueva propuesta en «{proyecto}»",
            f"Hola, {r['nombres']}:\n\n{quien['nombres']} {quien['apellidos']} propuso "
            f"{'la actividad' if tipo == 'actividad' else 'el producto'} «{_titulo(tipo, registro_id)}» "
            f"para el proyecto «{proyecto}».\n\nPuede aprobarlo o rechazarlo en:\n"
            f"{_url_proyecto(pid, 'pendientes')}\n\n"
            "(Puede desactivar estos avisos en «Mi perfil».)")


def revision(tipo: str, registro_id: int, pid: int, estado: str, revisor: int, comentario: str | None = None):
    """A quien propuso: su propuesta fue aprobada o rechazada (con el motivo)."""
    tabla = "actividad_proyecto" if tipo == "actividad" else "producto_proyecto"
    col = "actividad_id" if tipo == "actividad" else "producto_id"
    fila = get_db().q(f"SELECT propuesto_por FROM {tabla} WHERE {col} = ? AND proyecto_id = ?", [registro_id, pid])
    if not fila or fila[0]["propuesto_por"] == revisor:
        return
    u = _usuario(fila[0]["propuesto_por"])
    if not _quiere(u):
        return
    proyecto = get_db().q("SELECT nombre FROM proyecto WHERE id = ?", [pid])[0]["nombre"]
    titulo = _titulo(tipo, registro_id)
    if estado == "aprobado":
        correo.enviar(u["email"], f"Aprobado en «{proyecto}»: {titulo}",
                      f"Hola, {u['nombres']}:\n\nSu propuesta «{titulo}» ya forma parte del proyecto "
                      f"«{proyecto}».\n\n{_url_proyecto(pid, 'actividades' if tipo == 'actividad' else 'productos')}")
    else:
        correo.enviar(u["email"], f"Propuesta rechazada en «{proyecto}»: {titulo}",
                      f"Hola, {u['nombres']}:\n\nSu propuesta «{titulo}» para el proyecto «{proyecto}» fue "
                      f"rechazada.\n\nMotivo: {comentario}\n\nSi corresponde, corrija el registro y guárdelo "
                      f"con la casilla del proyecto marcada para volver a proponerlo:\n{config.URL_BASE}/proyectos")


# --- Propuestas institucionales ------------------------------------------------------------------

def _url_propuesta(prop_id: int) -> str:
    return f"{config.URL_BASE}/propuestas/{prop_id}"


def _responsables(pid: int) -> list[dict]:
    return get_db().q(
        """SELECT u.* FROM proyecto_participante pp JOIN usuario u ON u.id = pp.investigador_id
           WHERE pp.proyecto_id = ? AND pp.rol IN ('responsable', 'co_responsable')
             AND (pp.fecha_hasta IS NULL OR pp.fecha_hasta >= date('now'))""", [pid])


def propuesta_enviada(prop: dict, reenvio: bool):
    """A la administración: hay una propuesta institucional por decidir."""
    periodo = f"{prop['periodo']}–{prop['periodo'] + 1}"
    for u in get_db().q("SELECT * FROM usuario WHERE es_admin = 1 AND activo = 1"):
        if u["id"] == prop["proponente_id"] or not _quiere(u):
            continue
        correo.enviar(
            u["email"], f"{'Propuesta corregida' if reenvio else 'Nueva propuesta'} institucional: «{prop['nombre']}»",
            f"Hola, {u['nombres']}:\n\n{prop['proponente']} "
            f"{'reenvió, con las condiciones atendidas,' if reenvio else 'presentó'} la propuesta "
            f"«{prop['nombre']}» ({'continuidad' if prop['modalidad'] == 'continuidad' else 'proyecto nuevo'}) "
            f"para el periodo {periodo}.\n\nPuede revisarla y decidir en:\n{_url_propuesta(prop['id'])}")


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
        if u["id"] == admin_id or not _quiere(u):
            continue
        correo.enviar(u["email"], f"Propuesta {estado}: «{prop['nombre']}»",
                      f"Hola, {u['nombres']}:\n\nLa propuesta «{prop['nombre']}» para el periodo {periodo} fue "
                      f"{estado}.\n\n{detalle}\n\n{_url_propuesta(prop['id'])}")


def recordatorio_continuidad(p: dict, periodo: int, cierre: str):
    """A los responsables de un proyecto institucional que termina: si no proponen continuidad,
    concluye el 30 de septiembre."""
    for u in _responsables(p["id"]):
        if not _quiere(u):
            continue
        correo.enviar(
            u["email"], f"Continuidad de «{p['nombre']}»: la convocatoria cierra el {cierre}",
            f"Hola, {u['nombres']}:\n\nEl proyecto institucional «{p['nombre']}» termina el {p['fecha_fin']}. "
            f"Si quiere continuarlo en el periodo {periodo}–{periodo + 1}, presente la propuesta de continuidad "
            f"antes del {cierre}; si no, el proyecto concluye en esa fecha.\n\n"
            f"{_url_proyecto(p['id'], 'resumen')}")
