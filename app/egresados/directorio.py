"""Directorio de egresados y mentoría (PLAN §50, etapa 5).

- El egresado figura **solo si lo acepta** (`perfil_egresado.visible` con su consentimiento) y **solo dentro del sistema**: lo ven los
  estudiantes con cuenta, los egresados con cuenta y el personal que gestiona egresados.
- Se le invita desde la lista de egresados: se le crea una cuenta sin contraseña y recibe un enlace de ingreso (7 días).
- **Mentoría:** el estudiante pide al egresado una mentoría, charla, pasantía, orientación de posgrado u oferta de empleo. El correo
  de cada uno solo se comparte cuando el egresado acepta (a cada quien le llega el del otro).
"""
import json
from datetime import timedelta

from app.comun import config, correo, estudiantes, notificaciones, tokens, usuarios
from app.comun.db import AHORA, auditar, get_db, transaccion
from app.egresados import egresados

OFRECE = {"charla": "Dar una charla", "mentoria": "Mentoría o consejo de carrera", "pasantia": "Pasantías o prácticas",
          "posgrado": "Orientación sobre posgrados", "empleo": "Ofertas de empleo"}
TIPOS_SOLICITUD = {"mentoria": "Mentoría o consejo de carrera", "charla": "Una charla", "pasantia": "Pasantía o prácticas",
                   "posgrado": "Orientación sobre posgrados", "empleo": "Oferta de empleo", "otra": "Otra"}
MAX_PENDIENTES = 3          # solicitudes pendientes de un estudiante a la vez
VIGENCIA_INVITACION = timedelta(days=7)
LOTE_INVITACIONES = 50


# --- Perfil ----------------------------------------------------------------------------------------------------

def perfil(externo_id: int) -> dict | None:
    filas = get_db().q("SELECT * FROM perfil_egresado WHERE externo_id = ?", [externo_id])
    if not filas:
        return None
    filas[0]["ofrece"] = json.loads(filas[0]["ofrece"] or "[]")
    return filas[0]


def guardar_perfil(externo_id: int, d: dict) -> list[str]:
    """Guarda el perfil. Para figurar en el directorio hay que aceptarlo y decir a qué se dedica."""
    if not estudiantes.es_egresado(externo_id):
        return ["Solo los egresados titulados figuran en el directorio."]
    errores = []
    quiere = str(d.get("visible") or "") in ("1", "on", "true")
    ocupacion = (d.get("ocupacion") or "").strip()
    if quiere and str(d.get("acepto") or "") not in ("1", "on", "true"):
        errores.append("Para figurar en el directorio debe aceptar que sus datos los vean los estudiantes y el personal de la Carrera.")
    if quiere and not ocupacion:
        errores.append("Cuente a qué se dedica para figurar en el directorio.")
    ofrece = [o for o in (d.get("ofrece") or []) if o in OFRECE]
    if any(len((d.get(k) or "")) > 300 for k in ("ocupacion", "institucion", "ciudad_pais", "areas")) or len(d.get("detalle") or "") > 1000:
        errores.append("Alguno de los textos es demasiado largo.")
    if errores:
        return errores
    previo = perfil(externo_id)
    consentimiento = (previo or {}).get("consentimiento_en")
    datos = {"visible": int(quiere), "ocupacion": ocupacion or None, "institucion": (d.get("institucion") or "").strip() or None,
             "ciudad_pais": (d.get("ciudad_pais") or "").strip() or None, "areas": (d.get("areas") or "").strip() or None,
             "ofrece": json.dumps(ofrece), "detalle": (d.get("detalle") or "").strip() or None}
    with transaccion():
        if not previo:
            get_db().t.perfil_egresado.insert(externo_id=externo_id, **datos)
        else:
            get_db().t.perfil_egresado.update(externo_id=externo_id, **datos)
        if quiere and not consentimiento:
            get_db().execute(f"UPDATE perfil_egresado SET consentimiento_en = {AHORA} WHERE externo_id = ?", [externo_id])
        get_db().execute(f"UPDATE perfil_egresado SET actualizado_en = {AHORA} WHERE externo_id = ?", [externo_id])
    auditar(None, "guardar_perfil_egresado", "persona_externa", externo_id, "visible" if quiere else "oculto")
    return []


def visibles(texto: str = "", ofrece: str = "") -> list[dict]:
    from app.comun.db import sin_tildes
    patron = f"%{sin_tildes(texto.strip())}%"
    filas = get_db().q(
        """SELECT p.*, pe.nombres, pe.apellidos, es.cohorte_anio, es.fecha_titulacion FROM perfil_egresado p
           JOIN persona_externa pe ON pe.id = p.externo_id
           JOIN estudiante es ON es.externo_id = pe.id AND es.estado = 'titulado' AND es.nivel = 'licenciatura'
           WHERE p.visible = 1 AND (:t = '' OR sin_tildes(pe.nombres || ' ' || pe.apellidos || ' ' || COALESCE(p.ocupacion, '') || ' '
                                    || COALESCE(p.institucion, '') || ' ' || COALESCE(p.areas, '')) LIKE :p)
           GROUP BY p.externo_id ORDER BY pe.apellidos, pe.nombres""", {"t": texto.strip(), "p": patron})
    for f in filas:
        f["ofrece"] = json.loads(f["ofrece"] or "[]")
    return [f for f in filas if not ofrece or ofrece in f["ofrece"]]


# --- Invitación ------------------------------------------------------------------------------------------------

def estado_directorio(externo_id: int) -> str:
    p = perfil(externo_id)
    return "visible" if p and p["visible"] else ("invitado" if p and p["invitado_en"] else "sin invitar")


def invitar(externo_id: int, uid: int | None) -> list[str]:
    """Crea la cuenta del egresado (si falta) y le envía el enlace de ingreso con la invitación al directorio."""
    filas = get_db().q("SELECT * FROM persona_externa WHERE id = ?", [externo_id])
    if not filas or not estudiantes.es_egresado(externo_id):
        return ["Solo se invita a egresados titulados."]
    p = filas[0]
    if not (p["email"] or "").strip():
        return ["El egresado no tiene correo registrado."]
    u = estudiantes.usuario_de(externo_id) or estudiantes.crear_cuenta(externo_id, uid)
    if not u:
        return ["El correo ya lo usa otra cuenta: corríjalo antes de invitar."]
    enlace = f"{config.URL_BASE}/acceso/{tokens.emitir(u['id'], 'acceso', VIGENCIA_INVITACION)}"
    correo.enviar(p["email"], f"Invitación al directorio de egresados · {config.NOMBRE_SISTEMA}",
                  f"Hola, {p['nombres']}:\n\nLa Carrera de Matemática arma un directorio de egresados para que los estudiantes puedan "
                  f"pedirles una charla, una mentoría, orientación sobre posgrados o contarles de oportunidades. Figurar es opcional y "
                  f"solo lo ven estudiantes y personal de la Carrera dentro del sistema.\n\nSi quiere participar (o solo ver el "
                  f"directorio), ingrese aquí (el enlace sirve una vez y durante 7 días):\n{enlace}\n\nLuego abra «Mi perfil de egresado».")
    get_db().execute(f"""INSERT INTO perfil_egresado (externo_id, invitado_en) VALUES (?, {AHORA})
                         ON CONFLICT(externo_id) DO UPDATE SET invitado_en = {AHORA}""", [externo_id])
    auditar(uid, "invitar_directorio", "persona_externa", externo_id)
    return []


def invitar_pendientes(uid: int | None, lote: int = LOTE_INVITACIONES) -> dict:
    """Invita a los egresados titulados con correo que aún no recibieron la invitación."""
    enviados = errores = 0
    for g in egresados.titulados():
        if enviados >= lote:
            break
        p = perfil(g["externo_id"])
        if p and p["invitado_en"] or not (g["email"] or "").strip():
            continue
        if invitar(g["externo_id"], uid):
            errores += 1
        else:
            enviados += 1
    return {"invitados": enviados, "con_problemas": errores}


# --- Mentoría ----------------------------------------------------------------------------------------------------

def _persona(externo_id: int) -> dict:
    return get_db().q("SELECT * FROM persona_externa WHERE id = ?", [externo_id])[0]


def solicitar(de_externo: int, a_externo: int, tipo: str, mensaje: str) -> list[str]:
    p = perfil(a_externo)
    mensaje = (mensaje or "").strip()
    if de_externo == a_externo:
        return ["No puede pedirse algo a sí mismo."]
    if not p or not p["visible"]:
        return ["Ese egresado no figura en el directorio."]
    if tipo not in TIPOS_SOLICITUD:
        return ["Elija qué necesita."]
    if not mensaje:
        return ["Cuéntele brevemente qué necesita."]
    if len(mensaje) > 1000:
        return ["El mensaje es demasiado largo (1000 caracteres como máximo)."]
    db = get_db()
    if db.q("SELECT COUNT(*) n FROM solicitud_mentoria WHERE de_externo_id = ? AND estado = 'pendiente'", [de_externo])[0]["n"] >= MAX_PENDIENTES:
        return [f"Ya tiene {MAX_PENDIENTES} solicitudes pendientes: espere las respuestas."]
    if db.q("SELECT 1 FROM solicitud_mentoria WHERE de_externo_id = ? AND a_externo_id = ? AND estado = 'pendiente'", [de_externo, a_externo]):
        return ["Ya le envió una solicitud a esta persona y aún no responde."]
    sid = db.t.solicitud_mentoria.insert(de_externo_id=de_externo, a_externo_id=a_externo, tipo=tipo, mensaje=mensaje)["id"]
    quien = _persona(de_externo)
    u = estudiantes.usuario_de(a_externo)
    # El correo del estudiante no se dice todavía: solo si el egresado acepta.
    notificaciones.avisar(usuarios.por_id(u["id"]) if u else None, "Un estudiante le pidió su ayuda",
                          f"{quien['nombres']} {quien['apellidos']} (estudiante de la Carrera) le pide: "
                          f"{TIPOS_SOLICITUD[tipo].lower()}. «{mensaje[:300]}»", "/estudiante/perfil-egresado")
    auditar(None, "solicitar_mentoria", "solicitud_mentoria", sid)
    return []


def recibidas(a_externo: int) -> list[dict]:
    return get_db().q("""SELECT s.*, pe.nombres, pe.apellidos, pe.email FROM solicitud_mentoria s
                         JOIN persona_externa pe ON pe.id = s.de_externo_id WHERE s.a_externo_id = ?
                         ORDER BY s.estado = 'pendiente' DESC, s.creada_en DESC, s.id DESC""", [a_externo])


def enviadas(de_externo: int) -> list[dict]:
    return get_db().q("""SELECT s.*, pe.nombres, pe.apellidos, pe.email AS correo_egresado, p.ocupacion FROM solicitud_mentoria s
                         JOIN persona_externa pe ON pe.id = s.a_externo_id
                         LEFT JOIN perfil_egresado p ON p.externo_id = s.a_externo_id
                         WHERE s.de_externo_id = ? ORDER BY s.creada_en DESC, s.id DESC""", [de_externo])


def responder(sid: int, a_externo: int, aceptar: bool) -> bool:
    filas = get_db().q("SELECT * FROM solicitud_mentoria WHERE id = ? AND a_externo_id = ? AND estado = 'pendiente'", [sid, a_externo])
    if not filas:
        return False
    s = filas[0]
    get_db().execute(f"UPDATE solicitud_mentoria SET estado = ?, respondida_en = {AHORA} WHERE id = ?",
                     ["aceptada" if aceptar else "rechazada", sid])
    egresado = _persona(a_externo)
    u = estudiantes.usuario_de(s["de_externo_id"])
    if aceptar:
        notificaciones.avisar(usuarios.por_id(u["id"]) if u else None, "Aceptaron su solicitud",
                              f"{egresado['nombres']} {egresado['apellidos']} aceptó ayudarle con: {TIPOS_SOLICITUD[s['tipo']].lower()}. "
                              f"Puede escribirle a {egresado['email']}.", "/estudiante/directorio")
    else:
        notificaciones.avisar(usuarios.por_id(u["id"]) if u else None, "Su solicitud no pudo atenderse",
                              f"{egresado['nombres']} {egresado['apellidos']} no puede ayudarle por ahora con: "
                              f"{TIPOS_SOLICITUD[s['tipo']].lower()}. Puede pedirle a otra persona del directorio.", "/estudiante/directorio")
    auditar(None, "responder_mentoria", "solicitud_mentoria", sid, "aceptada" if aceptar else "rechazada")
    return True


def indicadores() -> dict:
    db = get_db()
    return {"invitados": db.q("SELECT COUNT(*) n FROM perfil_egresado WHERE invitado_en IS NOT NULL")[0]["n"],
            "visibles": db.q("SELECT COUNT(*) n FROM perfil_egresado WHERE visible = 1")[0]["n"],
            "solicitudes": db.q("SELECT COUNT(*) n FROM solicitud_mentoria")[0]["n"],
            "aceptadas": db.q("SELECT COUNT(*) n FROM solicitud_mentoria WHERE estado = 'aceptada'")[0]["n"],
            "por_tipo": {t: db.q("SELECT COUNT(*) n FROM solicitud_mentoria WHERE tipo = ?", [k])[0]["n"]
                         for k, t in TIPOS_SOLICITUD.items()}}
