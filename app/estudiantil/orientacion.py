"""Bienestar y orientación del estudiante (PLAN §67, etapa 9): preguntas frecuentes, directorio de servicios de apoyo y buzón de
consultas, reclamos y sugerencias. La Dirección de Carrera y la Coordinación académica atienden el buzón. Una consulta puede ir
**anónima**: no se guarda quién la envió ni la hora (solo el día) y no tiene respuesta personal; se responde publicándola en las
preguntas frecuentes."""
from datetime import date

from app.comun import estudiantes, notificaciones, permisos, usuarios
from app.comun.db import AHORA, auditar, get_db, transaccion

TIPOS = {"consulta": "Consulta", "reclamo": "Reclamo", "sugerencia": "Sugerencia"}
ESTADOS = {"recibida": "Recibida", "en_atencion": "En atención", "respondida": "Respondida", "cerrada": "Cerrada"}
TIPOS_SERVICIO = {"bienestar": "Bienestar universitario", "psicologia": "Apoyo psicológico", "salud": "Salud",
                  "economica": "Ayuda económica", "academica": "Apoyo académico", "otro": "Otro"}


def puede_gestionar(auth: dict | None) -> bool:
    return bool(auth) and permisos.puede(auth, "gestionar_buzon")


def _gestores() -> list[dict]:
    res = []
    for u in usuarios.listar():
        completo = usuarios.por_id(u["id"])
        if u["activo"] and permisos.puede(completo, "gestionar_buzon"):
            res.append(completo)
    return res


# --- Preguntas frecuentes y servicios -----------------------------------------------------------------------------------------

def preguntas(solo_publicadas: bool = True) -> list[dict]:
    return get_db().q(f"SELECT * FROM pregunta_frecuente {'WHERE publicada = 1' if solo_publicadas else ''} "
                      "ORDER BY categoria, orden, id")


def guardar_pregunta(d: dict, uid: int, pid: int | None = None) -> list[str]:
    categoria, pregunta, respuesta = ((d.get(k) or "").strip() for k in ("categoria", "pregunta", "respuesta"))
    if not categoria or len(categoria) > 60:
        return ["Escriba la categoría (hasta 60 caracteres)."]
    if not pregunta or len(pregunta) > 300:
        return ["Escriba la pregunta (hasta 300 caracteres)."]
    if not respuesta or len(respuesta) > 5000:
        return ["Escriba la respuesta (hasta 5.000 caracteres)."]
    x = {"categoria": categoria, "pregunta": pregunta, "respuesta": respuesta,
         "publicada": int(str(d.get("publicada", "1")) in ("1", "on"))}
    if pid:
        get_db().t.pregunta_frecuente.update(id=pid, **x)
    else:
        pid = get_db().t.pregunta_frecuente.insert(creada_por=uid, **x)["id"]
    auditar(uid, "guardar_pregunta_frecuente", "pregunta_frecuente", pid, pregunta[:100])
    return []


def eliminar_pregunta(pid: int, uid: int):
    get_db().execute("DELETE FROM pregunta_frecuente WHERE id = ?", [pid])
    auditar(uid, "eliminar_pregunta_frecuente", "pregunta_frecuente", pid)


def servicios(solo_activos: bool = True) -> list[dict]:
    return get_db().q(f"SELECT * FROM servicio_apoyo {'WHERE activo = 1' if solo_activos else ''} ORDER BY orden, nombre")


def guardar_servicio(d: dict, uid: int, sid: int | None = None) -> list[str]:
    nombre = (d.get("nombre") or "").strip()
    if not nombre or len(nombre) > 150:
        return ["Escriba el nombre del servicio (hasta 150 caracteres)."]
    if d.get("tipo") not in TIPOS_SERVICIO:
        return ["Elija el tipo de servicio."]
    enlace = (d.get("enlace") or "").strip()
    if enlace and not enlace.lower().startswith(("http://", "https://")):
        return ["El enlace debe empezar con http:// o https://."]
    x = {"tipo": d["tipo"], "nombre": nombre, "descripcion": (d.get("descripcion") or "").strip()[:1000] or None,
         "contacto": (d.get("contacto") or "").strip()[:300] or None, "horario": (d.get("horario") or "").strip()[:200] or None,
         "enlace": enlace or None, "activo": int(str(d.get("activo", "1")) in ("1", "on"))}
    if sid:
        get_db().t.servicio_apoyo.update(id=sid, **x)
    else:
        sid = get_db().t.servicio_apoyo.insert(**x)["id"]
    auditar(uid, "guardar_servicio_apoyo", "servicio_apoyo", sid, nombre)
    return []


def eliminar_servicio(sid: int, uid: int):
    get_db().execute("DELETE FROM servicio_apoyo WHERE id = ?", [sid])
    auditar(uid, "eliminar_servicio_apoyo", "servicio_apoyo", sid)


# --- Buzón ------------------------------------------------------------------------------------------------------------------------

def enviar(externo_id: int, tipo: str, asunto: str, texto: str, anonima: bool) -> list[str]:
    asunto, texto = (asunto or "").strip(), (texto or "").strip()
    if tipo not in TIPOS:
        return ["Elija si es una consulta, un reclamo o una sugerencia."]
    if not asunto or len(asunto) > 150:
        return ["Escriba el asunto (hasta 150 caracteres)."]
    if len(texto) < 10 or len(texto) > 4000:
        return ["Cuente su consulta con un poco más de detalle (de 10 a 4.000 caracteres)."]
    if anonima:
        # Anónima: sin quién la envió y solo con el día (no se audita ni se enlaza con la cuenta).
        cid = get_db().t.consulta.insert(tipo=tipo, asunto=asunto, texto=texto, anonima=1, externo_id=None,
                                         creada_en=date.today().isoformat())["id"]
    else:
        cid = get_db().t.consulta.insert(tipo=tipo, asunto=asunto, texto=texto, anonima=0, externo_id=externo_id,
                                         creada_en=get_db().q(f"SELECT {AHORA} AS t")[0]["t"])["id"]
    for g in _gestores():
        notificaciones.avisar(g, f"{TIPOS[tipo]} nueva en el buzón" + (" (anónima)" if anonima else ""), asunto, f"/servicios/buzon/{cid}")
    return []


def obtener(cid: int) -> dict | None:
    f = get_db().q("""SELECT c.*, pe.nombres, pe.apellidos, pe.email FROM consulta c LEFT JOIN persona_externa pe ON pe.id = c.externo_id
                      WHERE c.id = ?""", [cid])
    return f[0] if f else None


def listar(estado: str = "") -> list[dict]:
    return get_db().q("""SELECT c.*, pe.nombres, pe.apellidos FROM consulta c LEFT JOIN persona_externa pe ON pe.id = c.externo_id
                         WHERE (:e = '' OR c.estado = :e) ORDER BY c.estado IN ('respondida', 'cerrada'), c.creada_en DESC, c.id DESC""",
                      {"e": estado})


def mias(externo_id: int) -> list[dict]:
    return get_db().q("SELECT * FROM consulta WHERE externo_id = ? ORDER BY id DESC", [externo_id])


def responder(cid: int, respuesta: str, auth: dict, publicar_en_faq: bool, categoria: str = "") -> list[str]:
    """Responde. Una consulta identificada recibe la respuesta en su portal (y un aviso); una anónima solo se responde publicándola
    en las preguntas frecuentes."""
    c = obtener(cid)
    if not c or not puede_gestionar(auth):
        return ["No puede atender esa consulta."]
    if c["estado"] in ("respondida", "cerrada"):
        return ["Esa consulta ya se respondió."]
    respuesta = (respuesta or "").strip()
    if not respuesta or len(respuesta) > 5000:
        return ["Escriba la respuesta (hasta 5.000 caracteres)."]
    if c["anonima"] and not publicar_en_faq:
        return ["Una consulta anónima no tiene a quién responder: publique la respuesta en las preguntas frecuentes."]
    with transaccion():
        pid = None
        if publicar_en_faq:
            pid = get_db().t.pregunta_frecuente.insert(categoria=(categoria or "").strip()[:60] or "Consultas", pregunta=c["asunto"],
                                                       respuesta=respuesta, creada_por=auth["id"])["id"]
        get_db().execute(f"""UPDATE consulta SET estado = 'respondida', respuesta = ?, respondida_por = ?, respondida_en = {AHORA},
                             pregunta_id = ? WHERE id = ?""", [respuesta, auth["id"], pid, cid])
        auditar(auth["id"], "responder_consulta", "consulta", cid, "anónima" if c["anonima"] else TIPOS[c["tipo"]])
        if c["externo_id"]:
            notificaciones.avisar(estudiantes.usuario_de(c["externo_id"]), f"Respondieron su {TIPOS[c['tipo']].lower()}: {c['asunto']}",
                                  respuesta[:200], "/estudiante/buzon")
    return []


def cambiar_estado(cid: int, estado: str, auth: dict) -> list[str]:
    c = obtener(cid)
    if not c or not puede_gestionar(auth) or estado not in ("en_atencion", "cerrada"):
        return ["No puede cambiar esa consulta."]
    get_db().execute("UPDATE consulta SET estado = ? WHERE id = ?", [estado, cid])
    return []
