"""Programa analítico por asignatura y gestión (PLAN §68, etapa 3).

Lo escribe el titular de la materia en esa gestión. El borrador es único por asignatura y gestión; publicar crea una versión
que ya no se edita (para cambiar algo se parte de la última y se publica otra). El estudiante ve la última versión publicada."""
from app.academico import gestiones
from app.comun.db import auditar, get_db, transaccion

CAMPOS = {"objetivos": "Objetivos", "contenido": "Contenido (unidades temáticas)", "metodologia": "Metodología",
          "evaluacion": "Evaluación", "bibliografia": "Bibliografía"}
AYUDAS = {"objetivos": "Lo que el estudiante podrá hacer o conocer al terminar.",
          "contenido": "Una unidad por línea, con sus temas.", "metodologia": "Cómo se dictará la materia.",
          "evaluacion": "Qué se evalúa, cuándo y con qué peso.", "bibliografia": "Una referencia por línea."}
OBLIGATORIOS = ("objetivos", "contenido")
MAX = 6000


def es_titular(uid: int, asignatura_id: int, gestion_id: int) -> bool:
    return bool(get_db().q(
        """SELECT 1 FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
           WHERE d.usuario_id = ? AND o.asignatura_id = ? AND o.gestion_id = ? AND d.rol = 'titular'
             AND d.hasta IS NULL AND o.retirada_en IS NULL LIMIT 1""", [uid, asignatura_id, gestion_id]))


def puede_editar(uid: int, asignatura_id: int, gestion_id: int) -> str | None:
    """→ el motivo por el que no puede escribir el programa, o None."""
    g = gestiones.obtener(gestion_id)
    if not g:
        return "La gestión no existe."
    if g["estado"] == "concluida":
        return "La gestión concluyó: su historial no se edita."
    if not es_titular(uid, asignatura_id, gestion_id):
        return "Solo el titular de la materia en esa gestión escribe su programa."
    return None


def borrador(asignatura_id: int, gestion_id: int) -> dict | None:
    f = get_db().q("SELECT * FROM programa_analitico WHERE asignatura_id = ? AND gestion_id = ? AND estado = 'borrador'",
                   [asignatura_id, gestion_id])
    return f[0] if f else None


def publicado(asignatura_id: int, gestion_id: int) -> dict | None:
    """La última versión publicada de la asignatura en esa gestión."""
    f = get_db().q("""SELECT p.*, u.nombres, u.apellidos FROM programa_analitico p JOIN usuario u ON u.id = p.autor_id
                      WHERE p.asignatura_id = ? AND p.gestion_id = ? AND p.estado = 'publicado'
                      ORDER BY p.version DESC LIMIT 1""", [asignatura_id, gestion_id])
    return f[0] if f else None


def vigente(asignatura_id: int) -> dict | None:
    """La última versión publicada de la asignatura, de la gestión más reciente (lo que ve el estudiante)."""
    f = get_db().q("""SELECT p.*, u.nombres, u.apellidos, g.anio, g.tipo FROM programa_analitico p
                      JOIN usuario u ON u.id = p.autor_id JOIN gestion_academica g ON g.id = p.gestion_id
                      WHERE p.asignatura_id = ? AND p.estado = 'publicado'
                      ORDER BY g.fecha_inicio DESC, p.version DESC LIMIT 1""", [asignatura_id])
    return f[0] if f else None


def versiones(asignatura_id: int, gestion_id: int) -> list[dict]:
    return get_db().q("""SELECT version, publicado_en FROM programa_analitico
                         WHERE asignatura_id = ? AND gestion_id = ? AND estado = 'publicado' ORDER BY version DESC""",
                      [asignatura_id, gestion_id])


def con_programa() -> set[int]:
    """Asignaturas con al menos una versión publicada (para mostrar el enlace en el plan del estudiante)."""
    return {f["asignatura_id"] for f in get_db().q("SELECT DISTINCT asignatura_id FROM programa_analitico WHERE estado = 'publicado'")}


def materias_de(uid: int) -> list[dict]:
    """Materias en que la persona es titular en gestiones que no concluyeron, con el estado de su programa."""
    filas = get_db().q(
        """SELECT DISTINCT a.id AS asignatura_id, a.sigla, a.nombre, g.id AS gestion_id FROM oferta_docente d
           JOIN oferta o ON o.id = d.oferta_id JOIN asignatura a ON a.id = o.asignatura_id
           JOIN gestion_academica g ON g.id = o.gestion_id
           WHERE d.usuario_id = ? AND d.rol = 'titular' AND d.hasta IS NULL AND o.retirada_en IS NULL
             AND g.estado <> 'concluida' ORDER BY g.fecha_inicio, a.sigla""", [uid])
    for f in filas:
        g = gestiones.obtener(f["gestion_id"])
        f["gestion"] = gestiones.codigo(g)
        f["fecha_inicio"] = g["fecha_inicio"]
        pub = publicado(f["asignatura_id"], f["gestion_id"])
        f["version"] = pub["version"] if pub else None
        f["borrador"] = borrador(f["asignatura_id"], f["gestion_id"]) is not None
    return filas


def _limpiar(datos: dict) -> dict:
    return {k: (datos.get(k) or "").strip() for k in CAMPOS}


def guardar(asignatura_id: int, gestion_id: int, uid: int, datos: dict) -> list[str]:
    motivo = puede_editar(uid, asignatura_id, gestion_id)
    if motivo:
        return [motivo]
    d = _limpiar(datos)
    largos = [CAMPOS[k] for k, v in d.items() if len(v) > MAX]
    if largos:
        return [f"{', '.join(largos)}: admite hasta {MAX} caracteres."]
    with transaccion():
        b = borrador(asignatura_id, gestion_id)
        if b:
            get_db().execute(f"UPDATE programa_analitico SET {', '.join(f'{k} = ?' for k in d)}, autor_id = ? WHERE id = ?",
                             [*d.values(), uid, b["id"]])
        else:
            get_db().execute(f"""INSERT INTO programa_analitico (asignatura_id, gestion_id, autor_id, {', '.join(d)})
                                 VALUES (?, ?, ?, {', '.join('?' for _ in d)})""", [asignatura_id, gestion_id, uid, *d.values()])
    return []


def partir_de_la_vigente(asignatura_id: int, gestion_id: int, uid: int) -> list[str]:
    """Crea el borrador copiando la última versión publicada de la asignatura (de cualquier gestión)."""
    motivo = puede_editar(uid, asignatura_id, gestion_id)
    if motivo:
        return [motivo]
    if borrador(asignatura_id, gestion_id):
        return ["Ya tiene un borrador: edítelo o descártelo."]
    v = vigente(asignatura_id)
    if not v:
        return ["Aún no hay un programa publicado de esta asignatura."]
    return guardar(asignatura_id, gestion_id, uid, v)


def faltantes(b: dict | None) -> list[str]:
    return [CAMPOS[k] for k in OBLIGATORIOS if not (b or {}).get(k)]


def publicar(asignatura_id: int, gestion_id: int, uid: int) -> list[str]:
    motivo = puede_editar(uid, asignatura_id, gestion_id)
    if motivo:
        return [motivo]
    b = borrador(asignatura_id, gestion_id)
    if not b:
        return ["No hay un borrador para publicar."]
    falta = faltantes(b)
    if falta:
        return [f"Complete antes de publicar: {', '.join(falta).lower()}."]
    g = gestiones.obtener(gestion_id)
    with transaccion():
        n = (get_db().q("""SELECT MAX(version) m FROM programa_analitico WHERE asignatura_id = ? AND gestion_id = ?""",
                        [asignatura_id, gestion_id])[0]["m"] or 0) + 1
        get_db().execute("""UPDATE programa_analitico SET estado = 'publicado', version = ?, autor_id = ?,
                            publicado_en = datetime('now') WHERE id = ?""", [n, uid, b["id"]])
        auditar(uid, "publicar_programa", "programa_analitico", b["id"],
                f"{gestiones.codigo(g)} asignatura {asignatura_id}, versión {n}")
    return []


def descartar(asignatura_id: int, gestion_id: int, uid: int) -> list[str]:
    motivo = puede_editar(uid, asignatura_id, gestion_id)
    if motivo:
        return [motivo]
    get_db().execute("DELETE FROM programa_analitico WHERE asignatura_id = ? AND gestion_id = ? AND estado = 'borrador'",
                     [asignatura_id, gestion_id])
    return []


def cobertura(gestion_id: int) -> list[dict]:
    """Para quien arma la oferta: cada asignatura ofertada con sus titulares y la versión publicada (o None)."""
    filas = get_db().q(
        """SELECT DISTINCT a.id AS asignatura_id, a.sigla, a.nombre FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id
           WHERE o.gestion_id = ? AND o.retirada_en IS NULL ORDER BY a.sigla""", [gestion_id])
    for f in filas:
        f["titulares"] = ", ".join(t["apellidos"] for t in get_db().q(
            """SELECT DISTINCT u.apellidos FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
               JOIN usuario u ON u.id = d.usuario_id WHERE o.gestion_id = ? AND o.asignatura_id = ? AND d.rol = 'titular'
               AND d.hasta IS NULL AND o.retirada_en IS NULL ORDER BY u.apellidos""", [gestion_id, f["asignatura_id"]]))
        pub = publicado(f["asignatura_id"], gestion_id)
        f["version"] = pub["version"] if pub else None
        f["publicado_en"] = pub["publicado_en"] if pub else None
    return filas


def pendientes_de(uid: int) -> list[dict]:
    """Materias del titular, en gestiones que no concluyeron, sin programa publicado."""
    return [m for m in materias_de(uid) if m["version"] is None]
