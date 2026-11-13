"""«Mi historial docente» y certificados de tribunal y tutoría (PLAN §68, etapa 6). No guardan nada: reúnen lo que ya está en el
sistema, solo de la propia persona, y calculan un código de verificación para cada certificado."""
import hashlib

from app.comun.db import get_db

CONCLUIDOS = ("aprobado", "defendido", "rechazado", "reprobado")      # estados en que un trámite de grado terminó
TIPOS_CERT = {"tutor_grado": "Tutoría de proyecto de grado", "tribunal_grado": "Tribunal de proyecto de grado",
              "tribunal_auxiliatura": "Tribunal de auxiliaturas"}


def materias(uid: int) -> list[dict]:
    """Paralelos que la persona dictó (o dicta), de la gestión más reciente a la más antigua."""
    filas = get_db().q(
        """SELECT g.id AS gestion_id, g.anio, g.tipo, g.estado AS estado_gestion, a.sigla, a.nombre, o.paralelo, d.rol,
                  o.retirada_en IS NOT NULL AS retirada, d.hasta
           FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id JOIN asignatura a ON a.id = o.asignatura_id
           JOIN gestion_academica g ON g.id = o.gestion_id WHERE d.usuario_id = ?
           ORDER BY g.fecha_inicio DESC, a.sigla, o.paralelo""", [uid])
    for f in filas:
        f["gestion"] = f"{f['tipo']}-{f['anio']}"
    return filas


def _tramites(uid: int, como: str) -> list[dict]:
    consulta = {"tutor": "SELECT t.id FROM tramite_grado t WHERE t.tutor_id = ? AND t.estado <> 'borrador'",
                "tribunal": "SELECT t.id FROM tramite_grado t JOIN tribunal_grado m ON m.tramite_id = t.id WHERE m.usuario_id = ?"}[como]
    from app.servicios import grado
    return [grado.obtener(f["id"]) for f in get_db().q(consulta + " ORDER BY t.id DESC", [uid])]


def proyectos(uid: int) -> list[dict]:
    return get_db().q(
        """SELECT p.id, p.nombre, p.estado, x.rol, x.fecha_desde, x.fecha_hasta FROM proyecto_participante x
           JOIN proyecto p ON p.id = x.proyecto_id WHERE x.investigador_id = ? ORDER BY x.fecha_desde DESC, p.nombre""", [uid])


def tutorados(uid: int) -> dict:
    """Cuántos estudiantes tuteló (solo cifras: lo que se habló en las reuniones es confidencial)."""
    f = get_db().q("""SELECT COUNT(*) AS total, SUM(hasta IS NULL) AS vigentes FROM tutoria_asignacion WHERE tutor_id = ?""", [uid])[0]
    return {"total": f["total"] or 0, "vigentes": f["vigentes"] or 0}


def historial(uid: int) -> dict:
    from app.servicios import auxiliaturas
    return {"materias": materias(uid), "tutor": _tramites(uid, "tutor"), "tribunal": _tramites(uid, "tribunal"),
            "auxiliaturas": auxiliaturas.items_de_miembro(uid), "proyectos": proyectos(uid), "tutorados": tutorados(uid)}


# --- Certificados -----------------------------------------------------------------------------------------------------------

def codigo(tipo: str, ref: int, uid: int) -> str:
    return "TAU-" + hashlib.sha256(f"{tipo}:{ref}:{uid}".encode()).hexdigest()[:10].upper()


def _cert(tipo: str, ref: int, uid: int, titulo: str, detalle: str, fecha: str | None, **extra) -> dict:
    return {"tipo": tipo, "ref": ref, "titulo": titulo, "detalle": detalle, "fecha": (fecha or "")[:10],
            "codigo": codigo(tipo, ref, uid), "usuario_id": uid, **extra}


def elegibles(uid: int) -> list[dict]:
    """Certificados que la persona puede emitir: tutorías y tribunales de grado ya concluidos y tribunales de auxiliaturas de
    convocatorias concluidas."""
    from app.servicios import grado
    res = []
    for como, tipo in (("tutor", "tutor_grado"), ("tribunal", "tribunal_grado")):
        for t in _tramites(uid, como):
            if t["estado"] in CONCLUIDOS:
                res.append(_cert(tipo, t["id"], uid, t["titulo"], f"{grado.TIPOS[t['tipo']]} de {t['nombres']} {t['apellidos']}",
                                 t.get("defensa_en") or t.get("enviado_en"), estado=grado.ESTADOS[t["estado"]], clase=grado.TIPOS[t["tipo"]],
                                 estudiante=f"{t['nombres']} {t['apellidos']}"))
    for i in get_db().q(
            """SELECT i.id, c.titulo, c.modalidad, c.examen, c.publicacion, g.anio, g.tipo AS gtipo FROM tribunal_auxiliatura m
               JOIN item_auxiliatura i ON i.id = m.item_id JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
               JOIN gestion_academica g ON g.id = c.gestion_id WHERE m.usuario_id = ? AND c.estado = 'concluida'
               ORDER BY c.id DESC""", [uid]):
        res.append(_cert("tribunal_auxiliatura", i["id"], uid, i["titulo"], f"Gestión {i['gtipo']}-{i['anio']}",
                         i["examen"] or i["publicacion"]))
    return sorted(res, key=lambda c: c["fecha"], reverse=True)


def obtener_cert(uid: int, tipo: str, ref: int) -> dict | None:
    return next((c for c in elegibles(uid) if c["tipo"] == tipo and c["ref"] == ref), None)


def verificar(texto: str) -> dict | None:
    """El certificado que corresponde a un código (de cualquier docente), con el nombre de la persona. None si no existe."""
    texto = (texto or "").strip().upper()
    if not texto.startswith("TAU-"):
        return None
    uids = {f["u"] for f in get_db().q(
        """SELECT tutor_id AS u FROM tramite_grado WHERE tutor_id IS NOT NULL UNION SELECT usuario_id FROM tribunal_grado
           UNION SELECT usuario_id FROM tribunal_auxiliatura""")}
    for uid in uids:
        for c in elegibles(uid):
            if c["codigo"] == texto:
                p = get_db().q("SELECT nombres, apellidos FROM usuario WHERE id = ?", [uid])[0]
                return {**c, "persona": f"{p['nombres']} {p['apellidos']}"}
    return None

