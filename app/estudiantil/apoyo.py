"""Apoyo estudiantil (PLAN §67, etapa 8). Dos cosas distintas:

- **Señales** que TAU observa de un estudiante (su estado, su último ciclo, sus reuniones de tutoría, las encuestas que no
  responde). Se calculan al momento, no se guardan como etiqueta y **solo las ve el estudiante**.
- **Casos** de apoyo: los abre el propio estudiante («pedir apoyo») o su tutor(a) o la Dirección de Carrera, avisándole. Los ven
  el estudiante, su tutor(a) y la Dirección. Ningún caso dura más de un semestre sin renovarse.
"""
from datetime import date, timedelta

from app.comun import estudiantes, notificaciones, permisos, usuarios
from app.comun.db import AHORA, auditar, get_db, transaccion
from app.estudiantil import cohortes, encuestas, tutoria

TEMAS = tutoria.TEMAS
DERIVACIONES = tutoria.DERIVACIONES
ESTADOS = {"abierto": "Abierto", "en_seguimiento": "En seguimiento", "cerrado": "Cerrado", "vencido": "Vencido"}
ORIGENES = {"estudiante": "Lo pidió el estudiante", "tutor": "Lo abrió su tutor(a)", "direccion": "Lo abrió la Dirección de Carrera"}
VIGENCIA = timedelta(days=180)            # un semestre
MESES_SIN_REUNION = 6


def senales(externo_id: int, hoy: date | None = None) -> list[dict]:
    """Lo que TAU observa del estudiante, con una frase que dice de dónde sale: [{clave, texto}]."""
    hoy = hoy or date.today()
    res = []
    e = get_db().q("""SELECT * FROM estudiante WHERE externo_id = ? AND cohorte_anio IS NOT NULL
                      ORDER BY desde DESC, id DESC LIMIT 1""", [externo_id])
    if e and e[0]["estado"] == "congelado":
        res.append({"clave": "congelado", "texto": "Su matrícula figura como congelada en los datos que la Carrera cargó."})
    if e and e[0]["estado"] == "cursando" and e[0]["ultimo_anio"] and e[0]["ultimo_ciclo"]:
        ultimo, actual = cohortes.ordinal(e[0]["ultimo_anio"], e[0]["ultimo_ciclo"]), cohortes.ordinal(*cohortes.ciclo_actual())
        if ultimo < actual - 1:
            res.append({"clave": "ciclo", "texto": f"Su último ciclo registrado es {cohortes.texto(e[0]['ultimo_anio'], e[0]['ultimo_ciclo'])}: "
                                                    "no figura en el ciclo más reciente."})
    tutor = estudiantes.tutor_de(externo_id)
    if tutor and e and e[0]["estado"] == "cursando":
        ultima = tutoria.fechas_de_reuniones(externo_id)
        limite = (hoy - timedelta(days=30 * MESES_SIN_REUNION)).isoformat()
        asignado = get_db().q("SELECT desde FROM tutoria_asignacion WHERE externo_id = ? AND hasta IS NULL", [externo_id])[0]["desde"]
        if (ultima[0] if ultima else asignado) < limite:
            res.append({"clave": "tutoria", "texto": f"Hace más de {MESES_SIN_REUNION} meses que no hay una reunión registrada con su tutor(a)."})
    n = len(encuestas.por_responder(externo_id))
    if n:
        res.append({"clave": "encuestas", "texto": f"Tiene {n} encuesta(s) de la Carrera por responder."})
    return res


# --- Casos ------------------------------------------------------------------------------------------------------------------

def _con_estado(c: dict, hoy: str | None = None) -> dict:
    """El estado efectivo: un caso abierto o en seguimiento cuya fecha de vencimiento pasó figura como vencido."""
    hoy = hoy or date.today().isoformat()
    c["vencido"] = c["estado"] != "cerrado" and c["vence_el"] < hoy
    c["estado_efectivo"] = "vencido" if c["vencido"] else c["estado"]
    return c


def obtener(cid: int) -> dict | None:
    f = get_db().q("""SELECT c.*, pe.nombres, pe.apellidos, pe.email, u.nombres AS por_nombres, u.apellidos AS por_apellidos
                      FROM caso_apoyo c JOIN persona_externa pe ON pe.id = c.externo_id JOIN usuario u ON u.id = c.abierto_por
                      WHERE c.id = ?""", [cid])
    return _con_estado(f[0]) if f else None


def casos_de(externo_id: int) -> list[dict]:
    return [_con_estado(c) for c in get_db().q(
        "SELECT * FROM caso_apoyo WHERE externo_id = ? ORDER BY id DESC", [externo_id])]


def puede_atender(auth: dict | None, c: dict) -> bool:
    """La Dirección de Carrera atiende todos; el tutor(a) vigente, los de sus tutorados."""
    return bool(auth) and (permisos.puede(auth, "gestionar_apoyo") or tutoria.es_tutor_de(auth["id"], c["externo_id"]))


def listar(auth: dict, incluir_cerrados: bool = False) -> list[dict]:
    filas = get_db().q("""SELECT c.*, pe.nombres, pe.apellidos FROM caso_apoyo c JOIN persona_externa pe ON pe.id = c.externo_id
                          ORDER BY c.vence_el""")
    res = [_con_estado(c) for c in filas if puede_atender(auth, c)]
    return res if incluir_cerrados else [c for c in res if c["estado"] != "cerrado"]


def mensajes(cid: int) -> list[dict]:
    return get_db().q("""SELECT m.*, u.nombres, u.apellidos FROM caso_apoyo_mensaje m JOIN usuario u ON u.id = m.usuario_id
                         WHERE m.caso_id = ? ORDER BY m.id""", [cid])


def _destinatarios_personal(externo_id: int) -> list[dict]:
    """El tutor(a) y quienes gestionan el apoyo (la Dirección de Carrera)."""
    res = {}
    tutor = estudiantes.tutor_de(externo_id)
    if tutor:
        res[tutor["id"]] = usuarios.por_id(tutor["id"])
    for u in usuarios.listar():
        completo = usuarios.por_id(u["id"])
        if u["activo"] and permisos.puede(completo, "gestionar_apoyo"):
            res[u["id"]] = completo
    return list(res.values())


def abrir(externo_id: int, tema: str, motivo: str, auth: dict, origen: str) -> tuple[int | None, list[str]]:
    """Abre un caso. `origen`: 'estudiante' (auth es la cuenta del propio estudiante), 'tutor' o 'direccion'."""
    motivo = (motivo or "").strip()
    errores = []
    if tema not in TEMAS:
        errores.append("Elija el tema.")
    if len(motivo) < 10:
        errores.append("Cuente con un poco más de detalle (al menos 10 caracteres).")
    if len(motivo) > 2000:
        errores.append("El texto admite hasta 2.000 caracteres.")
    if any(not c["vencido"] and c["estado"] != "cerrado" for c in casos_de(externo_id)):
        errores.append("Ya hay un caso de apoyo abierto: use ese.")
    if origen == "tutor" and not tutoria.es_tutor_de(auth["id"], externo_id):
        errores.append("Solo su tutor(a) puede abrirlo como tutor(a).")
    if origen == "direccion" and not permisos.puede(auth, "gestionar_apoyo"):
        errores.append("Solo la Dirección de Carrera puede abrirlo.")
    if errores:
        return None, errores
    p = get_db().q("SELECT nombres, apellidos FROM persona_externa WHERE id = ?", [externo_id])[0]
    with transaccion():
        cid = get_db().t.caso_apoyo.insert(externo_id=externo_id, origen=origen, abierto_por=auth["id"], tema=tema, motivo=motivo,
                                           vence_el=(date.today() + VIGENCIA).isoformat())["id"]
        auditar(auth["id"], "abrir_caso_apoyo", "persona_externa", externo_id, f"{origen}: {TEMAS[tema]}")
        if origen == "estudiante":
            for u in _destinatarios_personal(externo_id):
                notificaciones.avisar(u, f"Pidió apoyo: {p['nombres']} {p['apellidos']}", f"Tema: {TEMAS[tema].lower()}.", f"/apoyo/{cid}")
        else:
            notificaciones.avisar(estudiantes.usuario_de(externo_id), "La Carrera le ofrece apoyo",
                                  f"{auth['nombres']} {auth['apellidos']} abrió un caso de apoyo: «{motivo[:200]}». Puede verlo y responder.",
                                  "/estudiante/apoyo")
    return cid, []


def responder(cid: int, texto: str, auth: dict, del_estudiante: bool) -> list[str]:
    c = obtener(cid)
    texto = (texto or "").strip()
    if not c or c["estado"] == "cerrado":
        return ["Ese caso está cerrado."]
    if not texto or len(texto) > 2000:
        return ["Escriba el mensaje (hasta 2.000 caracteres)."]
    get_db().t.caso_apoyo_mensaje.insert(caso_id=cid, usuario_id=auth["id"], del_estudiante=int(del_estudiante), texto=texto)
    get_db().execute(f"UPDATE caso_apoyo SET actualizado_en = {AHORA} WHERE id = ?", [cid])
    if del_estudiante:
        for u in _destinatarios_personal(c["externo_id"]):
            notificaciones.avisar(u, f"Mensaje de {c['nombres']} {c['apellidos']}", texto[:200], f"/apoyo/{cid}")
    else:
        notificaciones.avisar(estudiantes.usuario_de(c["externo_id"]), "Respuesta a su caso de apoyo", texto[:200], "/estudiante/apoyo")
    return []


def cambiar_estado(cid: int, estado: str, auth: dict, derivacion: str | None = None) -> list[str]:
    c = obtener(cid)
    if not c or not puede_atender(auth, c):
        return ["No puede atender ese caso."]
    if estado not in ("en_seguimiento", "cerrado"):
        return ["Estado no válido."]
    if c["estado"] == "cerrado":
        return ["Ese caso ya está cerrado."]
    der = derivacion if derivacion in DERIVACIONES else c["derivacion"]
    get_db().execute(f"UPDATE caso_apoyo SET estado = ?, derivacion = ?, actualizado_en = {AHORA}, "
                     f"cerrado_en = {AHORA if estado == 'cerrado' else 'NULL'} WHERE id = ?", [estado, der, cid])
    auditar(auth["id"], "atender_caso_apoyo", "caso_apoyo", cid, estado)
    if estado == "cerrado":
        notificaciones.avisar(estudiantes.usuario_de(c["externo_id"]), "Se cerró su caso de apoyo", "Puede pedir apoyo otra vez cuando lo necesite.",
                              "/estudiante/apoyo")
    return []


def renovar(cid: int, auth: dict) -> list[str]:
    c = obtener(cid)
    if not c or not puede_atender(auth, c) or c["estado"] == "cerrado":
        return ["No puede renovar ese caso."]
    get_db().execute(f"UPDATE caso_apoyo SET vence_el = ?, actualizado_en = {AHORA} WHERE id = ?",
                     [(date.today() + VIGENCIA).isoformat(), cid])
    auditar(auth["id"], "renovar_caso_apoyo", "caso_apoyo", cid)
    return []


def cerrar_por_el_estudiante(cid: int, externo_id: int) -> list[str]:
    c = obtener(cid)
    if not c or c["externo_id"] != externo_id or c["estado"] == "cerrado":
        return ["No hay un caso para cerrar."]
    get_db().execute(f"UPDATE caso_apoyo SET estado = 'cerrado', cerrado_en = {AHORA}, actualizado_en = {AHORA} WHERE id = ?", [cid])
    return []
