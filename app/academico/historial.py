"""«Mi historial docente» y certificados de tribunal y tutoría (PLAN §68, etapa 6). No guardan nada: reúnen lo que ya está en el
sistema, solo de la propia persona, y calculan un código de verificación para cada certificado.

Las materias son de este módulo; las tutorías y tribunales de grado, los tribunales de auxiliaturas, los proyectos y los
tutorados los aporta cada módulo activo (puntos `historial`, `certificados` y `titulares_de_certificados`; PLAN §73)."""
from app.comun import certificados, modulos
from app.comun.db import get_db


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


SECCIONES_VACIAS = {"tutor": [], "tribunal": [], "auxiliaturas": [], "proyectos": [], "tutorados": {"total": 0, "vigentes": 0}}


def secciones(uid: int) -> list[dict]:
    """Lo que aporta cada módulo activo al historial (punto `historial`), en su orden:
    {clave, orden, titulo, vacio, datos, filas: [{texto, detalle, insignia, href}]} o, en vez de filas, una `nota`."""
    return sorted((s for aporte in modulos.aportes("historial") for s in aporte(uid)), key=lambda s: s["orden"])


def historial(uid: int) -> dict:
    """Los datos del historial por clave: las materias (de este módulo) y lo que aportan los demás."""
    return {"materias": materias(uid), **SECCIONES_VACIAS, **{s["clave"]: s["datos"] for s in secciones(uid)}}


# --- Certificados -----------------------------------------------------------------------------------------------------------

codigo = certificados.codigo


def elegibles(uid: int) -> list[dict]:
    """Certificados que la persona puede emitir, del más reciente al más antiguo: los aporta cada módulo activo (tutorías
    y tribunales de grado ya concluidos, tribunales de auxiliaturas de convocatorias concluidas)."""
    res = [c for aporte in modulos.aportes("certificados") for c in aporte(uid)]
    return sorted(res, key=lambda c: c["fecha"], reverse=True)


def obtener_cert(uid: int, tipo: str, ref: int) -> dict | None:
    return next((c for c in elegibles(uid) if c["tipo"] == tipo and c["ref"] == ref), None)


def verificar(texto: str) -> dict | None:
    """El certificado que corresponde a un código (de cualquier docente), con el nombre de la persona. None si no existe."""
    texto = (texto or "").strip().upper()
    if not texto.startswith("TAU-"):
        return None
    uids = {u for aporte in modulos.aportes("titulares_de_certificados") for u in aporte()}
    for uid in uids:
        for c in elegibles(uid):
            if c["codigo"] == texto:
                p = get_db().q("SELECT nombres, apellidos FROM usuario WHERE id = ?", [uid])[0]
                return {**c, "persona": f"{p['nombres']} {p['apellidos']}"}
    return None
