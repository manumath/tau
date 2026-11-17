"""Banco de temas de grado (PLAN §67, etapa 5): los docentes con vínculo publican temas de tesis o proyecto de grado; el
estudiante pide tutor sobre un tema y, si el docente acepta, empieza su perfil con ese título y ese tutor."""
from app.comun import estudiantes, notificaciones, permisos, usuarios
from app.comun.db import AHORA, auditar, get_db, transaccion
from app.servicios import grado

MODALIDADES = {"cualquiera": "Proyecto de grado o tesis", **grado.MODALIDADES}
ESTADOS = {"borrador": "Borrador", "publicado": "Publicado", "retirado": "Retirado"}
ESTADOS_SOLICITUD = {"pendiente": "Pendiente", "aceptada": "Aceptada", "rechazada": "No aceptada", "retirada": "Retirada"}
MAX_PENDIENTES = 3          # solicitudes pendientes de un estudiante a la vez


def puede_publicar(auth: dict | None) -> bool:
    """Docentes con vínculo vigente con la Carrera (los mismos que pueden ser tutores) y quien gestiona el grado."""
    return bool(auth) and (auth["id"] in {u["id"] for u in grado.tutores()} or permisos.puede(auth, "gestionar_grado"))


def puede_gestionar(auth: dict | None, t: dict) -> bool:
    return bool(auth) and (t["docente_id"] == auth["id"] or permisos.puede(auth, "gestionar_grado"))


def obtener(tid: int) -> dict | None:
    f = get_db().q("""SELECT t.*, u.nombres, u.apellidos, l.nombre AS linea,
                             (SELECT COUNT(*) FROM solicitud_tema s WHERE s.tema_id = t.id AND s.estado = 'aceptada') AS aceptadas
                      FROM tema_grado t JOIN usuario u ON u.id = t.docente_id
                      LEFT JOIN linea_investigacion l ON l.id = t.linea_id WHERE t.id = ?""", [tid])
    return f[0] if f else None


def listar(auth: dict) -> list[dict]:
    filas = get_db().q(
        """SELECT t.*, u.nombres, u.apellidos,
                  (SELECT COUNT(*) FROM solicitud_tema s WHERE s.tema_id = t.id AND s.estado = 'pendiente') AS pendientes,
                  (SELECT COUNT(*) FROM solicitud_tema s WHERE s.tema_id = t.id AND s.estado = 'aceptada') AS aceptadas
           FROM tema_grado t JOIN usuario u ON u.id = t.docente_id
           ORDER BY t.estado = 'retirado', t.estado = 'publicado' DESC, t.id DESC""")
    return [t for t in filas if puede_gestionar(auth, t)]


def validar(d: dict) -> tuple[dict, list[str]]:
    errores = []
    titulo = (d.get("titulo") or "").strip()
    if not titulo or len(titulo) > 300:
        errores.append("El título es obligatorio (hasta 300 caracteres).")
    modalidad = d.get("modalidad") if d.get("modalidad") in MODALIDADES else "cualquiera"
    cupos = (d.get("cupos") or "1").strip()
    if not cupos.isdigit() or not 1 <= int(cupos) <= 10:
        errores.append("Los cupos son un número entero de 1 a 10.")
    for campo, limite in (("descripcion", 5000), ("requisitos", 2000)):
        if len(d.get(campo) or "") > limite:
            errores.append(f"«{campo}» admite hasta {limite} caracteres.")
    linea = int(d["linea_id"]) if str(d.get("linea_id") or "").isdigit() else None
    return ({"titulo": titulo, "descripcion": (d.get("descripcion") or "").strip() or None,
             "requisitos": (d.get("requisitos") or "").strip() or None, "linea_id": linea, "modalidad": modalidad,
             "cupos": int(cupos) if cupos.isdigit() else 1}, errores)


def crear(d: dict, auth: dict) -> tuple[int | None, list[str]]:
    if not puede_publicar(auth):
        return None, ["Solo los docentes con vínculo con la Carrera publican temas."]
    x, errores = validar(d)
    if errores:
        return None, errores
    tid = get_db().t.tema_grado.insert(docente_id=auth["id"], **x)["id"]
    auditar(auth["id"], "crear_tema_grado", "tema_grado", tid, x["titulo"])
    return tid, []


def actualizar(tid: int, d: dict, auth: dict) -> list[str]:
    t = obtener(tid)
    if not t or not puede_gestionar(auth, t) or t["estado"] == "retirado":
        return ["No puede editar ese tema."]
    x, errores = validar(d)
    if not errores and x["cupos"] < t["aceptadas"]:
        errores.append(f"Ya aceptó a {t['aceptadas']} estudiante(s): los cupos no pueden ser menos.")
    if errores:
        return errores
    get_db().t.tema_grado.update(id=tid, **x)
    return []


def cambiar_estado(tid: int, estado: str, auth: dict) -> list[str]:
    t = obtener(tid)
    if not t or not puede_gestionar(auth, t):
        return ["No puede cambiar ese tema."]
    if estado == "publicado" and t["estado"] == "borrador":
        get_db().execute(f"UPDATE tema_grado SET estado = 'publicado', publicado_en = {AHORA} WHERE id = ?", [tid])
    elif estado == "retirado" and t["estado"] in ("borrador", "publicado"):
        get_db().execute("UPDATE tema_grado SET estado = 'retirado' WHERE id = ?", [tid])
    else:
        return ["Ese cambio de estado no corresponde."]
    return []


# --- Estudiante -------------------------------------------------------------------------------------------------------------

def disponibles(texto: str = "", linea: str = "", modalidad: str = "") -> list[dict]:
    """Temas publicados con cupo, con el nombre del docente."""
    filas = get_db().q(
        """SELECT t.*, u.nombres, u.apellidos, l.nombre AS linea,
                  (SELECT COUNT(*) FROM solicitud_tema s WHERE s.tema_id = t.id AND s.estado = 'aceptada') AS aceptadas
           FROM tema_grado t JOIN usuario u ON u.id = t.docente_id LEFT JOIN linea_investigacion l ON l.id = t.linea_id
           WHERE t.estado = 'publicado' AND u.activo = 1 ORDER BY t.publicado_en DESC, t.id DESC""")
    texto = (texto or "").strip().lower()
    return [t for t in filas if t["aceptadas"] < t["cupos"]
            and (not texto or texto in f"{t['titulo']} {t['descripcion'] or ''} {t['apellidos']}".lower())
            and (not linea or str(t["linea_id"]) == linea) and (not modalidad or t["modalidad"] in (modalidad, "cualquiera"))]


def solicitud_de(tid: int, externo_id: int) -> dict | None:
    f = get_db().q("SELECT * FROM solicitud_tema WHERE tema_id = ? AND externo_id = ?", [tid, externo_id])
    return f[0] if f else None


def mis_solicitudes(externo_id: int) -> list[dict]:
    return get_db().q("""SELECT s.*, t.titulo, t.modalidad, t.docente_id, u.nombres, u.apellidos FROM solicitud_tema s
                         JOIN tema_grado t ON t.id = s.tema_id JOIN usuario u ON u.id = t.docente_id
                         WHERE s.externo_id = ? ORDER BY s.id DESC""", [externo_id])


def solicitar(tid: int, externo_id: int, mensaje: str) -> list[str]:
    t = obtener(tid)
    if not t or t["estado"] != "publicado":
        return ["Ese tema no está disponible."]
    if t["aceptadas"] >= t["cupos"]:
        return ["Ese tema ya no tiene cupos."]
    if any(x["tipo"] == "perfil" and x["estado"] in grado.ABIERTOS + ("aprobado",) for x in grado.de_estudiante(externo_id)):
        return ["Ya tiene un perfil de grado en curso o aprobado."]
    mensaje = (mensaje or "").strip()
    if len(mensaje) > 1000:
        return ["El mensaje admite hasta 1.000 caracteres."]
    previa = solicitud_de(tid, externo_id)
    if previa and previa["estado"] != "retirada":
        return ["Ya pidió este tema."]
    if sum(s["estado"] == "pendiente" for s in mis_solicitudes(externo_id)) >= MAX_PENDIENTES:
        return [f"Puede tener hasta {MAX_PENDIENTES} solicitudes pendientes a la vez."]
    with transaccion():
        if previa:
            get_db().execute("UPDATE solicitud_tema SET estado = 'pendiente', mensaje = ?, respuesta = NULL, respondida_en = NULL "
                             "WHERE id = ?", [mensaje or None, previa["id"]])
        else:
            get_db().t.solicitud_tema.insert(tema_id=tid, externo_id=externo_id, mensaje=mensaje or None)
        p = get_db().q("SELECT nombres, apellidos FROM persona_externa WHERE id = ?", [externo_id])[0]
        notificaciones.avisar(usuarios.por_id(t["docente_id"]), f"Pidieron su tema: {t['titulo']}",
                              f"{p['nombres']} {p['apellidos']} le pide ser su tutor(a).", f"/servicios/temas/{tid}")
    return []


def retirar(tid: int, externo_id: int) -> list[str]:
    s = solicitud_de(tid, externo_id)
    if not s or s["estado"] != "pendiente":
        return ["No hay una solicitud pendiente para retirar."]
    get_db().execute("UPDATE solicitud_tema SET estado = 'retirada' WHERE id = ?", [s["id"]])
    return []


def solicitudes(tid: int) -> list[dict]:
    return get_db().q("""SELECT s.*, pe.nombres, pe.apellidos, pe.email, es.registro_universitario FROM solicitud_tema s
                         JOIN persona_externa pe ON pe.id = s.externo_id
                         LEFT JOIN estudiante es ON es.id = (SELECT MAX(id) FROM estudiante WHERE externo_id = pe.id)
                         WHERE s.tema_id = ? AND s.estado <> 'retirada' ORDER BY s.id""", [tid])


def responder(sid: int, acepta: bool, respuesta: str, auth: dict) -> list[str]:
    f = get_db().q("SELECT * FROM solicitud_tema WHERE id = ?", [sid])
    t = obtener(f[0]["tema_id"]) if f else None
    if not f or not t or not puede_gestionar(auth, t) or f[0]["estado"] != "pendiente":
        return ["Esa solicitud no está pendiente."]
    if acepta and t["aceptadas"] >= t["cupos"]:
        return ["El tema ya no tiene cupos."]
    respuesta = (respuesta or "").strip()[:500]
    with transaccion():
        get_db().execute(f"UPDATE solicitud_tema SET estado = ?, respuesta = ?, respondida_en = {AHORA} WHERE id = ?",
                         ["aceptada" if acepta else "rechazada", respuesta or None, sid])
        notificaciones.avisar(estudiantes.usuario_de(f[0]["externo_id"]),
                              ("Aceptaron su pedido de tutoría: " if acepta else "Su pedido de tutoría no fue aceptado: ") + t["titulo"],
                              respuesta or ("Ya puede empezar su perfil con este tema." if acepta else ""), "/estudiante/temas")
        auditar(auth["id"], "responder_solicitud_tema", "tema_grado", t["id"], "aceptada" if acepta else "rechazada")
    return []


def aceptado_para(externo_id: int, tid: int) -> dict | None:
    """El tema, si el docente aceptó a este estudiante (para empezar el perfil con ese título y ese tutor)."""
    s = solicitud_de(tid, externo_id)
    return obtener(tid) if s and s["estado"] == "aceptada" else None
