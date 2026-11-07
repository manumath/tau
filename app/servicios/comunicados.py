"""Comunicados, convocatorias y eventos (PLAN §58, servicio 1).

- Los publica una cuenta con cargo (Dirección de Carrera, Dirección del Instituto, Coordinación académica) o el
  responsable de un proyecto, «como» ese cargo o ese proyecto. Se arman en borrador y se publican.
- **Para todos** llega a todas las cuentas activas; si no, a los **convocados**: grupos (estudiantes, una cohorte,
  docentes de la Carrera, participantes de un proyecto, tesistas, postulantes de una convocatoria) y personas sueltas.
  El responsable de un proyecto solo usa el grupo de su proyecto y personas sueltas.
- Un evento puede pedir **confirmar asistencia** (Asistiré / No podré). Si no es para todos, el organizador registra
  después quién asistió (decisión 9 del 7-nov-2026).
- Al publicar, cada destinatario recibe un aviso (campana y correo según su preferencia).
"""
from datetime import datetime

from app.comun import estudiantes, notificaciones, permisos, usuarios
from app.comun.db import AHORA, get_db, sin_tildes, transaccion, vigente_hasta

TIPOS = {"comunicado": "Comunicado", "convocatoria": "Convocatoria", "evento": "Evento"}
CARGOS = {"direccion_carrera": "Dirección de Carrera", "direccion_instituto": "Dirección del Instituto",
          "coordinacion_academica": "Coordinación académica"}
RESPUESTAS = {"asistire": "Asistiré", "no_podre": "No podré"}
ESTADOS = {"borrador": "Borrador", "publicado": "Publicado", "cancelado": "Cancelado"}


# --- Quién publica -----------------------------------------------------------------------------------------------

def proyectos_que_dirige(uid: int) -> list[dict]:
    return get_db().q(f"""SELECT p.id, p.nombre FROM proyecto p JOIN proyecto_participante pp ON pp.proyecto_id = p.id
                         WHERE pp.investigador_id = ? AND pp.rol IN ('responsable', 'co_responsable')
                           AND {vigente_hasta('pp.fecha_hasta')}
                           AND p.estado <> 'finalizado' ORDER BY p.nombre""", [uid])


def como_puede_publicar(auth: dict) -> list[tuple[str, str]]:
    """[(valor, texto)]: los cargos vigentes del usuario y los proyectos que dirige («proyecto:7»)."""
    if not auth or auth.get("solo_estudiante"):
        return []
    opciones = [(c, t) for c, t in CARGOS.items() if permisos.tiene_rol(auth, c)]
    opciones += [(f"proyecto:{p['id']}", f"Responsable de «{p['nombre']}»") for p in proyectos_que_dirige(auth["id"])]
    return opciones


def puede_publicar(auth: dict) -> bool:
    return bool(como_puede_publicar(auth))


def autor(c: dict) -> str:
    if c["publica_como"] == "proyecto":
        p = get_db().q("SELECT nombre FROM proyecto WHERE id = ?", [c["proyecto_id"]])
        return f"Proyecto «{p[0]['nombre']}»" if p else "Proyecto"
    return CARGOS[c["publica_como"]]


def puede_editar(auth: dict, c: dict) -> bool:
    """Quien lo creó, o quien hoy tiene el mismo cargo o dirige el mismo proyecto."""
    if not auth or not c:
        return False
    if c["creado_por"] == auth["id"]:
        return True
    valor = f"proyecto:{c['proyecto_id']}" if c["publica_como"] == "proyecto" else c["publica_como"]
    return valor in dict(como_puede_publicar(auth))


# --- Grupos de convocados -----------------------------------------------------------------------------------------

def grupos(auth: dict, c: dict) -> list[tuple[str, str]]:
    """Grupos que puede convocar quien arma el comunicado `c`."""
    if c["publica_como"] == "proyecto":
        return [(f"proyecto:{c['proyecto_id']}", "Participantes del proyecto")]
    db = get_db()
    res = [("estudiantes", "Todos los estudiantes con cuenta"), ("docentes", "Docentes de la Carrera"),
           ("grado", "Estudiantes con un trámite de grado en curso")]
    res += [(f"cohorte:{f['cohorte_anio']}", f"Cohorte {f['cohorte_anio']}")
            for f in db.q("""SELECT DISTINCT e.cohorte_anio FROM estudiante e JOIN cuenta_estudiante c ON c.externo_id = e.externo_id
                             WHERE e.cohorte_anio IS NOT NULL ORDER BY e.cohorte_anio DESC""")]
    res += [(f"auxiliatura:{f['id']}", f"Postulantes: {f['titulo']}")
            for f in db.q("SELECT id, titulo FROM convocatoria_auxiliatura WHERE estado <> 'borrador' ORDER BY id DESC LIMIT 10")]
    res += [(f"proyecto:{p['id']}", f"Participantes de «{p['nombre']}»") for p in proyectos_que_dirige(auth["id"])]
    return res


def miembros_de(grupo: str) -> list[int]:
    db = get_db()
    clave, _, valor = grupo.partition(":")
    activos = "JOIN usuario u ON u.id = c.usuario_id AND u.activo = 1"
    if clave == "estudiantes":
        filas = db.q(f"SELECT c.usuario_id FROM cuenta_estudiante c {activos}")
    elif clave == "cohorte" and valor.isdigit():
        filas = db.q(f"""SELECT DISTINCT c.usuario_id FROM cuenta_estudiante c {activos}
                         JOIN estudiante e ON e.externo_id = c.externo_id WHERE e.cohorte_anio = ?""", [int(valor)])
    elif clave == "docentes":
        filas = [{"usuario_id": u["id"]} for u in usuarios.listar() if u["activo"] and u["categoria"]]
    elif clave == "grado":
        filas = db.q(f"""SELECT DISTINCT c.usuario_id FROM cuenta_estudiante c {activos}
                         JOIN tramite_grado t ON t.externo_id = c.externo_id
                         WHERE t.estado NOT IN ('rechazado', 'defendido', 'reprobado')""")
    elif clave == "auxiliatura" and valor.isdigit():
        filas = db.q(f"""SELECT DISTINCT c.usuario_id FROM cuenta_estudiante c {activos}
                         JOIN postulacion_auxiliatura p ON p.externo_id = c.externo_id
                         JOIN item_auxiliatura i ON i.id = p.item_id
                         WHERE i.convocatoria_id = ? AND p.estado <> 'borrador'""", [int(valor)])
    elif clave == "proyecto" and valor.isdigit():
        filas = db.q(f"""SELECT pp.investigador_id AS usuario_id FROM proyecto_participante pp
                        JOIN usuario u ON u.id = pp.investigador_id AND u.activo = 1
                        WHERE pp.proyecto_id = :p AND {vigente_hasta('pp.fecha_hasta')}
                        UNION SELECT c.usuario_id FROM proyecto_participante pp JOIN cuenta_estudiante c ON c.externo_id = pp.externo_id
                        JOIN usuario u ON u.id = c.usuario_id AND u.activo = 1
                        WHERE pp.proyecto_id = :p AND {vigente_hasta('pp.fecha_hasta')}""",
                     {"p": int(valor)})
    else:
        filas = []
    return [f["usuario_id"] for f in filas]


def buscar_personas(texto: str, limite: int = 8) -> list[dict]:
    """Cuentas activas (personal y estudiantes) cuyo nombre o correo coincide."""
    texto = texto.strip()
    if len(texto) < 2:
        return []
    patron = f"%{sin_tildes(texto)}%"
    return get_db().q("""SELECT u.id, u.nombres, u.apellidos, u.email,
                                EXISTS (SELECT 1 FROM cuenta_estudiante c WHERE c.usuario_id = u.id) AS estudiante
                         FROM usuario u WHERE u.activo = 1 AND (sin_tildes(u.email) LIKE :p
                               OR sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p
                               OR sin_tildes(u.apellidos || ' ' || u.nombres) LIKE :p)
                         ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres) LIMIT :l""", {"p": patron, "l": limite})


# --- Comunicados ------------------------------------------------------------------------------------------------

def obtener(cid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM comunicado WHERE id = ?", [cid])
    return filas[0] if filas else None


def validar(d: dict, opciones: list[tuple[str, str]]) -> tuple[dict, list[str]]:
    errores = []
    tipo = d.get("tipo") or ""
    if tipo not in TIPOS:
        errores.append("Elija el tipo.")
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        errores.append("Escriba el título.")
    como = d.get("publica_como") or ""
    if como not in dict(opciones):
        errores.append("Elija en nombre de quién se publica.")
    inicio = (d.get("inicio") or "").strip() or None
    if tipo == "evento":
        try:
            datetime.fromisoformat(inicio or "")
        except ValueError:
            errores.append("Indique la fecha y la hora del evento.")
    x = {"tipo": tipo, "titulo": titulo[:200], "texto": (d.get("texto") or "").strip()[:8000],
         "publica_como": "proyecto" if como.startswith("proyecto:") else como,
         "proyecto_id": int(como.split(":")[1]) if como.startswith("proyecto:") else None,
         "inicio": inicio if tipo == "evento" else None,
         "lugar": ((d.get("lugar") or "").strip()[:200] or None) if tipo == "evento" else None,
         "confirmar": 1 if tipo == "evento" and str(d.get("confirmar") or "") in ("1", "on") else 0,
         "enlace": (d.get("enlace") or "").strip()[:300] or None}
    if x["enlace"] and not x["enlace"].startswith("/"):
        errores.append("El enlace debe ser una dirección dentro del sistema (empieza con /).")
    return x, errores


def crear(x: dict, uid: int) -> int:
    return get_db().t.comunicado.insert(creado_por=uid, **x)["id"]


def editar(cid: int, x: dict):
    get_db().t.comunicado.update(id=cid, **x)


def eliminar(cid: int):
    get_db().execute("DELETE FROM comunicado WHERE id = ? AND estado = 'borrador'", [cid])


def fijar_para_todos(cid: int, valor: bool):
    get_db().execute("UPDATE comunicado SET para_todos = ? WHERE id = ?", [int(valor), cid])


def convocados(cid: int) -> list[dict]:
    return get_db().q("""SELECT d.*, u.nombres, u.apellidos, u.email,
                                EXISTS (SELECT 1 FROM cuenta_estudiante c WHERE c.usuario_id = u.id) AS estudiante
                         FROM comunicado_destinatario d JOIN usuario u ON u.id = d.usuario_id
                         WHERE d.comunicado_id = ? ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres)""", [cid])


def agregar_convocados(cid: int, uids: list[int], excluir: int | None = None) -> int:
    """Agrega sin repetir. → cuántos nuevos."""
    ya = {d["usuario_id"] for d in get_db().q("SELECT usuario_id FROM comunicado_destinatario WHERE comunicado_id = ?", [cid])}
    nuevos = [u for u in dict.fromkeys(uids) if u not in ya and u != excluir]
    with transaccion():
        for u in nuevos:
            get_db().t.comunicado_destinatario.insert(comunicado_id=cid, usuario_id=u)
    return len(nuevos)


def quitar_convocado(cid: int, uid: int):
    get_db().execute("DELETE FROM comunicado_destinatario WHERE comunicado_id = ? AND usuario_id = ?", [cid, uid])


def vaciar_convocados(cid: int):
    get_db().execute("DELETE FROM comunicado_destinatario WHERE comunicado_id = ?", [cid])


def alcance(c: dict) -> int:
    """A cuántas personas llegará (o llegó)."""
    if c["para_todos"] and c["estado"] == "borrador":
        return get_db().q("SELECT COUNT(*) n FROM usuario WHERE activo = 1 AND id <> ?", [c["creado_por"]])[0]["n"]
    return get_db().q("SELECT COUNT(*) n FROM comunicado_destinatario WHERE comunicado_id = ?", [c["id"]])[0]["n"]


def url_para(uid: int, cid: int) -> str:
    """La pantalla del comunicado según quién lo recibe (las cuentas de estudiante solo llegan a /estudiante)."""
    u = usuarios.con_perfil(uid)
    if u and estudiantes.cuenta_de(uid):
        u["roles"] = permisos.roles_vigentes(uid)
        if estudiantes.solo_estudiante(u):
            return f"/estudiante/comunicados/{cid}"
    return f"/servicios/comunicados/{cid}"


def publicar(cid: int) -> list[str]:
    c = obtener(cid)
    if not c or c["estado"] != "borrador":
        return ["Solo se publica un borrador."]
    if c["tipo"] == "evento" and not c["inicio"]:
        return ["Indique la fecha y la hora del evento."]
    with transaccion():
        if c["para_todos"]:
            vaciar_convocados(cid)
            agregar_convocados(cid, [f["id"] for f in get_db().q("SELECT id FROM usuario WHERE activo = 1")],
                               excluir=c["creado_por"])
        elif not convocados(cid):
            return ["Agregue al menos un convocado, o márquelo para todos."]
        get_db().execute(f"UPDATE comunicado SET estado = 'publicado', publicado_en = {AHORA} WHERE id = ?", [cid])
        asunto = f"{TIPOS[c['tipo']]}: {c['titulo']}"
        texto = f"{autor(c)}" + (f" · {fecha_hora(c['inicio'])}" if c["inicio"] else "") + \
            (" · Le pedimos confirmar si asistirá." if c["confirmar"] else "")
        for d in convocados(cid):
            notificaciones.avisar(usuarios.por_id(d["usuario_id"]), asunto, texto, url_para(d["usuario_id"], cid))
    return []


def cancelar(cid: int) -> list[str]:
    c = obtener(cid)
    if not c or c["estado"] != "publicado":
        return ["Solo se cancela lo publicado."]
    with transaccion():
        get_db().execute("UPDATE comunicado SET estado = 'cancelado' WHERE id = ?", [cid])
        for d in convocados(cid):
            notificaciones.avisar(usuarios.por_id(d["usuario_id"]), f"Cancelado: {c['titulo']}",
                                  f"{autor(c)} canceló este {TIPOS[c['tipo']].lower()}.", url_para(d["usuario_id"], cid))
    return []


# --- Lo que recibe cada persona -----------------------------------------------------------------------------------

def recibidos(uid: int, limite: int = 50) -> list[dict]:
    return get_db().q("""SELECT c.*, d.respuesta, d.asistio FROM comunicado c
                         JOIN comunicado_destinatario d ON d.comunicado_id = c.id AND d.usuario_id = ?
                         WHERE c.estado <> 'borrador' ORDER BY c.publicado_en DESC, c.id DESC LIMIT ?""", [uid, limite])


def recibido(uid: int, cid: int) -> dict | None:
    filas = get_db().q("""SELECT c.*, d.respuesta, d.asistio FROM comunicado c
                          JOIN comunicado_destinatario d ON d.comunicado_id = c.id AND d.usuario_id = ?
                          WHERE c.id = ? AND c.estado <> 'borrador'""", [uid, cid])
    return filas[0] if filas else None


def por_confirmar(uid: int) -> list[dict]:
    """Eventos publicados, por venir, que piden confirmar y la persona aún no responde."""
    ahora = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return [c for c in recibidos(uid) if c["estado"] == "publicado" and c["confirmar"] and not c["respuesta"]
            and (c["inicio"] or "") >= ahora]


def responder(uid: int, cid: int, respuesta: str) -> list[str]:
    c = recibido(uid, cid)
    if not c or c["estado"] != "publicado" or not c["confirmar"]:
        return ["Este comunicado no pide confirmar asistencia."]
    if respuesta not in RESPUESTAS:
        return ["Respuesta no válida."]
    if (c["inicio"] or "") < datetime.now().strftime("%Y-%m-%dT%H:%M"):
        return ["El evento ya empezó."]
    get_db().execute(f"""UPDATE comunicado_destinatario SET respuesta = ?, respondido_en = {AHORA}
                         WHERE comunicado_id = ? AND usuario_id = ?""", [respuesta, cid, uid])
    return []


def mios(auth: dict) -> list[dict]:
    """Lo que la persona creó o puede editar por su cargo, con cifras."""
    filas = get_db().q("""SELECT c.*, (SELECT COUNT(*) FROM comunicado_destinatario d WHERE d.comunicado_id = c.id) AS n,
                                 (SELECT COUNT(*) FROM comunicado_destinatario d WHERE d.comunicado_id = c.id
                                    AND d.respuesta = 'asistire') AS asistiran
                          FROM comunicado c ORDER BY c.estado <> 'borrador', c.publicado_en DESC, c.id DESC""")
    return [c for c in filas if puede_editar(auth, c)]


def puede_registrar_asistencia(c: dict) -> bool:
    return (c["tipo"] == "evento" and c["estado"] == "publicado" and not c["para_todos"]
            and (c["inicio"] or "9999") <= datetime.now().strftime("%Y-%m-%dT%H:%M"))


def registrar_asistencia(cid: int, presentes: set[int]):
    with transaccion():
        for d in convocados(cid):
            get_db().execute("UPDATE comunicado_destinatario SET asistio = ? WHERE comunicado_id = ? AND usuario_id = ?",
                             [int(d["usuario_id"] in presentes), cid, d["usuario_id"]])


def cifras(cid: int) -> dict:
    ds = convocados(cid)
    return {"total": len(ds), "asistire": sum(d["respuesta"] == "asistire" for d in ds),
            "no_podre": sum(d["respuesta"] == "no_podre" for d in ds),
            "sin_respuesta": sum(not d["respuesta"] for d in ds),
            "asistieron": sum(d["asistio"] == 1 for d in ds), "registrada": any(d["asistio"] is not None for d in ds)}


def fecha_hora(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        f = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre")
    return f"{dias[f.weekday()]} {f.day} de {meses[f.month - 1]} de {f.year}" + (f", {f:%H:%M}" if "T" in iso or " " in iso else "")
