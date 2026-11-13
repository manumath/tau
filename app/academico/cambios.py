"""Cambios con el semestre activo (PLAN §66, etapa 3): agregar o retirar una materia, y agregar, reasignar o retirar un
docente, siempre con motivo y fecha de efecto. No se borra nada: la materia retirada queda con su fecha y su motivo, y el
docente que cambia conserva su fila con el primer y el último día en que dictó. Cada cambio queda en `gestion_cambio` y
en la auditoría, y se avisa al docente que entra o sale.

Las gestiones en planificación se editan sin motivo (`app.academico.oferta`); las concluidas son historial.
"""
from datetime import date, timedelta

from app.academico import gestiones, oferta
from app.comun import formato, notificaciones, usuarios
from app.comun.db import auditar, get_db, transaccion

MOTIVOS = {"renuncia": "Renuncia", "fallecimiento": "Fallecimiento", "licencia": "Licencia o baja",
           "reasignacion": "Reasignación", "falta_inscritos": "Falta de inscritos",
           "error_planificacion": "Error de planificación", "necesidad": "Necesidad académica", "otro": "Otro"}
TIPOS = {"agregar_materia": "Materia agregada", "retirar_materia": "Materia retirada",
         "agregar_docente": "Docente agregado", "reasignar_docente": "Docente reasignado",
         "retirar_docente": "Docente retirado"}


def exige_motivo(g: dict) -> bool:
    """Con la gestión activa, todo cambio de la oferta o de los docentes pide motivo y fecha."""
    return g["estado"] == "activa"


def _fecha(g: dict, f: dict, errores: list) -> str | None:
    try:
        d = date.fromisoformat((f.get("fecha") or "").strip())
    except ValueError:
        errores.append("Indique la fecha de efecto.")
        return None
    if not g["fecha_inicio"] <= d.isoformat() <= g["fecha_fin"]:
        errores.append(f"La fecha de efecto debe estar entre el inicio y el término de {gestiones.codigo(g)} "
                       f"({g['fecha_inicio']} a {g['fecha_fin']}).")
        return None
    return d.isoformat()


def _motivo(f: dict, errores: list) -> tuple[str | None, str | None]:
    motivo, detalle = (f.get("motivo") or "").strip(), (f.get("detalle") or "").strip()
    if motivo not in MOTIVOS:
        errores.append("Elija el motivo del cambio.")
    elif motivo == "otro" and not detalle:
        errores.append("Con el motivo «Otro», explique qué ocurrió.")
    if len(detalle) > 500:
        errores.append("El detalle admite hasta 500 caracteres.")
    return motivo, detalle or None


def _dia_anterior(fecha: str, minimo: str) -> str:
    return max((date.fromisoformat(fecha) - timedelta(days=1)).isoformat(), minimo)


def _activa(oid: int) -> tuple[dict | None, dict | None, list[str]]:
    o = oferta.obtener(oid)
    g = gestiones.obtener(o["gestion_id"]) if o else None
    if not o or not g:
        return None, None, ["El paralelo no existe."]
    if not exige_motivo(g):
        return o, g, ["Los cambios con motivo solo se hacen con la gestión activa."]
    if o["retirada_en"]:
        return o, g, ["Esa materia ya fue retirada."]
    return o, g, []


def _registrar(g, tipo, fecha, o_sigla, o_paralelo, asignatura_id, anterior, nuevo, rol, motivo, detalle, uid):
    get_db().t.gestion_cambio.insert(
        gestion_id=g["id"], fecha_efecto=fecha, tipo=tipo, asignatura_id=asignatura_id, paralelo=o_paralelo,
        docente_anterior_id=anterior, docente_nuevo_id=nuevo, rol=rol, motivo=motivo, detalle=detalle,
        registrado_por=uid)
    auditar(uid, tipo, "gestion_academica", g["id"],
            f"{gestiones.codigo(g)} {o_sigla} {o_paralelo}: desde el {formato.fecha(fecha)}, {MOTIVOS[motivo].lower()}"
            + (f" ({detalle})" if detalle else ""))


def _avisar(usuario_id, asunto, texto, g, uid):
    if usuario_id and usuario_id != uid:
        notificaciones.avisar(usuarios.por_id(usuario_id), asunto, texto, "/docencia")


def agregar_materia(gid: int, sigla: str, paralelo: str, inscritos, f: dict, uid: int) -> list[str]:
    g = gestiones.obtener(gid)
    if not g or not exige_motivo(g):
        return ["Los cambios con motivo solo se hacen con la gestión activa."]
    errores = []
    fecha = _fecha(g, f, errores)
    motivo, detalle = _motivo(f, errores)
    if errores:
        return errores
    with transaccion():
        oid, errores = oferta.agregar(gid, sigla, paralelo, inscritos, uid)
        if errores:
            return errores
        get_db().execute("UPDATE oferta SET agregada_en = ? WHERE id = ?", [fecha, oid])
        o = oferta.obtener(oid)
        _registrar(g, "agregar_materia", fecha, o["sigla"], o["paralelo"], o["asignatura_id"], None, None, None,
                   motivo, detalle, uid)
    return []


def retirar_materia(oid: int, f: dict, uid: int) -> list[str]:
    o, g, errores = _activa(oid)
    if errores:
        return errores
    fecha = _fecha(g, f, errores)
    motivo, detalle = _motivo(f, errores)
    if errores:
        return errores
    with transaccion():
        get_db().execute("UPDATE oferta SET retirada_en = ?, motivo_retiro = ? WHERE id = ?", [fecha, MOTIVOS[motivo], oid])
        vigentes = oferta.docentes(oid)
        for d in vigentes:
            get_db().execute("UPDATE oferta_docente SET hasta = ? WHERE id = ?",
                             [_dia_anterior(fecha, d["desde"] or g["fecha_inicio"]), d["id"]])
        _registrar(g, "retirar_materia", fecha, o["sigla"], o["paralelo"], o["asignatura_id"], None, None, None,
                   motivo, detalle, uid)
        for d in vigentes:
            _avisar(d["usuario_id"], f"Se retiró {o['sigla']} de {gestiones.codigo(g)}",
                    f"La materia {o['sigla']} {o['nombre']} (paralelo {o['paralelo']}) se retiró de la oferta desde el "
                    f"{formato.fecha(fecha)}. Motivo: {MOTIVOS[motivo].lower()}.", g, uid)
    return []


def _docente_vigente(did: int) -> tuple[dict | None, dict | None, dict | None, list[str]]:
    filas = get_db().q("SELECT * FROM oferta_docente WHERE id = ?", [did])
    if not filas:
        return None, None, None, ["La asignación no existe."]
    d = filas[0]
    o, g, errores = _activa(d["oferta_id"])
    if not errores and d["hasta"]:
        errores = ["Esa persona ya dejó el paralelo."]
    return d, o, g, errores


def agregar_docente(oid: int, usuario_id: int, rol: str, f: dict, uid: int) -> list[str]:
    o, g, errores = _activa(oid)
    if errores:
        return errores
    fecha = _fecha(g, f, errores)
    motivo, detalle = _motivo(f, errores)
    if errores:
        return errores
    with transaccion():
        errores = oferta.asignar(oid, usuario_id, rol)
        if errores:
            return errores
        get_db().execute("UPDATE oferta_docente SET desde = ? WHERE oferta_id = ? AND usuario_id = ?",
                         [fecha, oid, usuario_id])
        _registrar(g, "agregar_docente", fecha, o["sigla"], o["paralelo"], o["asignatura_id"], None, usuario_id, rol,
                   motivo, detalle, uid)
        _avisar(usuario_id, f"Se le asignó {o['sigla']} en {gestiones.codigo(g)}",
                f"Desde el {formato.fecha(fecha)} dicta {o['sigla']} {o['nombre']} (paralelo {o['paralelo']}) como "
                f"{oferta.ROLES[rol].lower()}.", g, uid)
    return []


def reasignar_docente(did: int, nuevo_id: int, f: dict, uid: int) -> list[str]:
    d, o, g, errores = _docente_vigente(did)
    if errores:
        return errores
    fecha = _fecha(g, f, errores)
    motivo, detalle = _motivo(f, errores)
    if fecha and fecha <= (d["desde"] or g["fecha_inicio"]):
        errores.append("La fecha de efecto debe ser posterior al día en que esa persona empezó a dictar el paralelo.")
    if nuevo_id == d["usuario_id"]:
        errores.append("Elija a otra persona: es la misma que ya dicta el paralelo.")
    if errores:
        return errores
    with transaccion():
        errores = oferta.asignar(o["id"], nuevo_id, d["rol"])
        if errores:
            return errores
        get_db().execute("UPDATE oferta_docente SET desde = ? WHERE oferta_id = ? AND usuario_id = ?",
                         [fecha, o["id"], nuevo_id])
        get_db().execute("UPDATE oferta_docente SET hasta = ? WHERE id = ?", [_dia_anterior(fecha, g["fecha_inicio"]), did])
        _registrar(g, "reasignar_docente", fecha, o["sigla"], o["paralelo"], o["asignatura_id"], d["usuario_id"],
                   nuevo_id, d["rol"], motivo, detalle, uid)
        _avisar(d["usuario_id"], f"Deja {o['sigla']} en {gestiones.codigo(g)}",
                f"Desde el {formato.fecha(fecha)} ya no dicta {o['sigla']} {o['nombre']} (paralelo {o['paralelo']}). Motivo: "
                f"{MOTIVOS[motivo].lower()}.", g, uid)
        _avisar(nuevo_id, f"Se le asignó {o['sigla']} en {gestiones.codigo(g)}",
                f"Desde el {formato.fecha(fecha)} dicta {o['sigla']} {o['nombre']} (paralelo {o['paralelo']}) como "
                f"{oferta.ROLES[d['rol']].lower()}.", g, uid)
    return []


def retirar_docente(did: int, f: dict, uid: int) -> list[str]:
    d, o, g, errores = _docente_vigente(did)
    if errores:
        return errores
    fecha = _fecha(g, f, errores)
    motivo, detalle = _motivo(f, errores)
    if fecha and fecha <= (d["desde"] or g["fecha_inicio"]):
        errores.append("La fecha de efecto debe ser posterior al día en que esa persona empezó a dictar el paralelo.")
    if errores:
        return errores
    with transaccion():
        get_db().execute("UPDATE oferta_docente SET hasta = ? WHERE id = ?", [_dia_anterior(fecha, g["fecha_inicio"]), did])
        _registrar(g, "retirar_docente", fecha, o["sigla"], o["paralelo"], o["asignatura_id"], d["usuario_id"], None,
                   d["rol"], motivo, detalle, uid)
        _avisar(d["usuario_id"], f"Deja {o['sigla']} en {gestiones.codigo(g)}",
                f"Desde el {formato.fecha(fecha)} ya no dicta {o['sigla']} {o['nombre']} (paralelo {o['paralelo']}). Motivo: "
                f"{MOTIVOS[motivo].lower()}.", g, uid)
    return []


def listar(gid: int) -> list[dict]:
    """El registro de cambios de la gestión, del más reciente al más antiguo."""
    return get_db().q(
        """SELECT c.*, a.sigla, a.nombre AS asignatura,
                  ua.nombres || ' ' || ua.apellidos AS anterior, un.nombres || ' ' || un.apellidos AS nuevo,
                  ur.nombres || ' ' || ur.apellidos AS por
           FROM gestion_cambio c LEFT JOIN asignatura a ON a.id = c.asignatura_id
           LEFT JOIN usuario ua ON ua.id = c.docente_anterior_id LEFT JOIN usuario un ON un.id = c.docente_nuevo_id
           LEFT JOIN usuario ur ON ur.id = c.registrado_por
           WHERE c.gestion_id = ? ORDER BY c.fecha_efecto DESC, c.id DESC""", [gid])
