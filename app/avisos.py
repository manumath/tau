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
