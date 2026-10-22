"""Actividad estudiantil declarada (PLAN §49): ayudantías, olimpiadas, pasantías, becas, movilidad, semilleros…

La declara el estudiante desde su cuenta (con evidencia opcional: PDF, PNG o JPG) y la verifica la Dirección de
Carrera o la Coordinación académica. Una actividad verificada que el estudiante edita vuelve a quedar
pendiente; una observada pide corregir algo y también vuelve a pendiente al corregirla.
"""
from datetime import date

from app.comun import notificaciones, usuarios
from app.comun.db import AHORA, auditar, get_db
from app.investigacion import adjuntos

ENTIDAD = "actividad_estudiantil"
TIPOS = {"ayudantia": "Ayudantía de docencia o investigación", "olimpiada": "Olimpiada o competencia",
         "congreso": "Congreso, seminario o taller", "pasantia": "Pasantía o práctica", "beca": "Beca o ayuda",
         "movilidad": "Movilidad o intercambio", "semillero": "Semillero o grupo de estudio",
         "charla": "Charla o divulgación", "voluntariado": "Voluntariado o extensión", "otra": "Otra"}
ESTADOS = {"pendiente": "Por verificar", "verificada": "Verificada", "observada": "Con observaciones"}


def listar(externo_id: int) -> list[dict]:
    filas = get_db().q("SELECT * FROM actividad_estudiantil WHERE externo_id = ? ORDER BY fecha_inicio DESC, id DESC",
                       [externo_id])
    for f in filas:
        f["evidencias"] = adjuntos.listar(ENTIDAD, f["id"])
    return filas


def obtener(aid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM actividad_estudiantil WHERE id = ?", [aid])
    if not filas:
        return None
    filas[0]["evidencias"] = adjuntos.listar(ENTIDAD, aid)
    return filas[0]


def validar(d: dict) -> tuple[dict, list[str]]:
    errores = []
    tipo = d.get("tipo")
    if tipo not in TIPOS:
        errores.append("Elija el tipo de actividad.")
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        errores.append("Escriba un título.")
    elif len(titulo) > 200:
        errores.append("El título es demasiado largo (200 caracteres como máximo).")
    inicio, fin = (d.get("fecha_inicio") or "").strip(), (d.get("fecha_fin") or "").strip()
    try:
        ini = date.fromisoformat(inicio)
        if ini > date.today():
            errores.append("La fecha de inicio no puede ser futura.")
        elif ini.year < 2000:
            errores.append("La fecha de inicio no es válida.")
    except ValueError:
        errores.append("Indique la fecha de inicio.")
    if fin:
        try:
            if date.fromisoformat(fin) < date.fromisoformat(inicio or "9999-12-31"):
                errores.append("La fecha de término no puede ser anterior al inicio.")
        except ValueError:
            errores.append("La fecha de término no es válida.")
    descripcion = (d.get("descripcion") or "").strip()
    if len(descripcion) > 2000:
        errores.append("La descripción es demasiado larga (2000 caracteres como máximo).")
    return {"tipo": tipo, "titulo": titulo, "descripcion": descripcion or None,
            "institucion": (d.get("institucion") or "").strip()[:200] or None,
            "fecha_inicio": inicio, "fecha_fin": fin or None}, errores


def crear(externo_id: int, d: dict) -> tuple[int | None, list[str]]:
    datos, errores = validar(d)
    if errores:
        return None, errores
    return get_db().t.actividad_estudiantil.insert(externo_id=externo_id, **datos)["id"], []


def editar(aid: int, d: dict) -> list[str]:
    datos, errores = validar(d)
    if not errores:
        get_db().execute(
            f"""UPDATE actividad_estudiantil SET tipo = :tipo, titulo = :titulo, descripcion = :descripcion,
                institucion = :institucion, fecha_inicio = :fecha_inicio, fecha_fin = :fecha_fin,
                estado = 'pendiente', observacion = NULL, verificado_por = NULL, verificado_en = NULL,
                actualizado_en = {AHORA} WHERE id = :id""", {**datos, "id": aid})
    return errores


def marcar_pendiente(aid: int):
    """Un cambio en la actividad o su evidencia la devuelve a «por verificar»."""
    get_db().execute(f"""UPDATE actividad_estudiantil SET estado = 'pendiente', observacion = NULL, verificado_por = NULL,
                         verificado_en = NULL, actualizado_en = {AHORA} WHERE id = ? AND estado != 'pendiente'""", [aid])


def eliminar(aid: int):
    adjuntos.eliminar_de(ENTIDAD, aid)
    get_db().execute("DELETE FROM adjunto WHERE entidad = ? AND entidad_id = ?", [ENTIDAD, aid])
    get_db().execute("DELETE FROM actividad_estudiantil WHERE id = ?", [aid])


# --- Verificación -------------------------------------------------------------------------------------------

def pendientes() -> list[dict]:
    """Actividades por verificar, las más antiguas primero, con el nombre del estudiante."""
    filas = get_db().q(
        """SELECT a.*, pe.nombres, pe.apellidos FROM actividad_estudiantil a JOIN persona_externa pe ON pe.id = a.externo_id
           WHERE a.estado = 'pendiente' ORDER BY a.actualizado_en, a.id""")
    for f in filas:
        f["evidencias"] = adjuntos.listar(ENTIDAD, f["id"])
    return filas


def n_pendientes() -> int:
    return get_db().q("SELECT COUNT(*) n FROM actividad_estudiantil WHERE estado = 'pendiente'")[0]["n"]


def _avisar(a: dict, asunto: str, texto: str):
    from app.comun import estudiantes
    u = estudiantes.usuario_de(a["externo_id"])
    if u:
        notificaciones.avisar(usuarios.por_id(u["id"]), asunto, texto, "/estudiante")


def verificar(aid: int, uid: int) -> bool:
    a = obtener(aid)
    if not a or a["estado"] != "pendiente":
        return False
    get_db().execute(f"""UPDATE actividad_estudiantil SET estado = 'verificada', observacion = NULL, verificado_por = ?,
                         verificado_en = {AHORA} WHERE id = ?""", [uid, aid])
    auditar(uid, "verificar_actividad_estudiantil", ENTIDAD, aid, a["titulo"])
    _avisar(a, "Su actividad fue verificada", f"«{a['titulo']}» quedó verificada.")
    return True


def observar(aid: int, uid: int, observacion: str) -> list[str]:
    a = obtener(aid)
    observacion = (observacion or "").strip()
    if not a or a["estado"] != "pendiente":
        return ["Esa actividad ya no está por verificar."]
    if not observacion:
        return ["Escriba qué debe corregir el estudiante."]
    get_db().execute(f"""UPDATE actividad_estudiantil SET estado = 'observada', observacion = ?, verificado_por = ?,
                         verificado_en = {AHORA} WHERE id = ?""", [observacion[:1000], uid, aid])
    auditar(uid, "observar_actividad_estudiantil", ENTIDAD, aid, a["titulo"])
    _avisar(a, "Su actividad tiene observaciones", f"«{a['titulo']}»: {observacion[:300]}")
    return []


def resumen_verificadas(desde_anio: int, hasta_anio: int) -> dict[str, int]:
    """Actividades verificadas por tipo cuyo inicio cae entre los años (para informes agregados)."""
    return {f["tipo"]: f["n"] for f in get_db().q(
        """SELECT tipo, COUNT(*) n FROM actividad_estudiantil WHERE estado = 'verificada'
           AND substr(fecha_inicio, 1, 4) BETWEEN ? AND ? GROUP BY tipo""", [str(desde_anio), str(hasta_anio)])}
