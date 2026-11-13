"""Preferencias del docente para la oferta de una gestión (PLAN §68, etapa 2).

El docente dice qué materias prefiere o no puede dictar y en qué turnos no tiene disponibilidad. Es una ayuda para quien arma
la oferta, nunca una asignación. Las ve la propia persona y quien tiene `gestionar_oferta`; se editan en planificación."""
from app.academico import gestiones, oferta
from app.comun import vinculos
from app.comun.db import auditar, get_db, transaccion

NIVELES = {"prefiere": "La prefiero", "no_puede": "No puedo dictarla"}
DIAS = {"lun": "Lunes", "mar": "Martes", "mie": "Miércoles", "jue": "Jueves", "vie": "Viernes", "sab": "Sábado"}
TURNOS = {"manana": "Mañana", "tarde": "Tarde", "noche": "Noche"}
MAX_NOTA = 300
MAX_COMENTARIO = 1000


def turnos_validos() -> set[str]:
    return {f"{d}-{t}" for d in DIAS for t in TURNOS}


def gestiones_abiertas() -> list[dict]:
    """Las gestiones donde aún se puede indicar preferencias (en planificación), de la más próxima a la más lejana."""
    return sorted((g for g in gestiones.listar() if gestiones.edicion_libre(g)), key=lambda g: g["fecha_inicio"])


def puede_indicar(uid: int, g: dict) -> str | None:
    """→ el motivo por el que no puede, o None. Pide vínculo vigente al inicio de la gestión o materias en la Carrera."""
    if not gestiones.edicion_libre(g):
        return "La gestión ya no está en planificación: los cambios los hace la Dirección de Carrera o la Coordinación."
    if vinculos.vigente(uid, g["fecha_inicio"]) is None and not get_db().q(
            "SELECT 1 FROM oferta_docente WHERE usuario_id = ? LIMIT 1", [uid]):
        return "Solo quienes tienen vínculo con la Carrera pueden indicar preferencias."
    return None


def de_persona(gid: int, uid: int) -> dict:
    """Lo que la persona indicó: {'materias': {asignatura_id: {nivel, nota}}, 'indisponible': set, 'comentario'}."""
    materias = {f["asignatura_id"]: {"nivel": f["nivel"], "nota": f["nota"] or ""} for f in get_db().q(
        "SELECT asignatura_id, nivel, nota FROM preferencia_oferta WHERE gestion_id = ? AND usuario_id = ?", [gid, uid])}
    g = get_db().q("SELECT indisponible, comentario FROM preferencia_gestion WHERE gestion_id = ? AND usuario_id = ?",
                   [gid, uid])
    return {"materias": materias, "indisponible": {x for x in (g[0]["indisponible"] if g else "").split(",") if x},
            "comentario": (g[0]["comentario"] or "") if g else ""}


def tiene(gid: int, uid: int) -> bool:
    return bool(get_db().q("""SELECT 1 FROM preferencia_oferta WHERE gestion_id = ? AND usuario_id = ?
                              UNION SELECT 1 FROM preferencia_gestion WHERE gestion_id = ? AND usuario_id = ? LIMIT 1""",
                           [gid, uid, gid, uid]))


def guardar(g: dict, uid: int, materias: dict[int, tuple[str, str]], indisponible: list[str], comentario: str) -> list[str]:
    """Reemplaza lo que la persona indicó para la gestión. `materias`: {asignatura_id: (nivel, nota)}."""
    motivo = puede_indicar(uid, g)
    if motivo:
        return [motivo]
    validas = {a["id"] for a in oferta.asignaturas_ofertables()}
    errores = []
    for aid, (nivel, nota) in materias.items():
        if aid not in validas:
            errores.append("Una de las asignaturas no existe.")
        elif nivel not in NIVELES:
            errores.append("Elija «La prefiero» o «No puedo dictarla».")
        elif len(nota or "") > MAX_NOTA:
            errores.append(f"Las notas de cada materia admiten hasta {MAX_NOTA} caracteres.")
    if len((comentario or "").strip()) > MAX_COMENTARIO:
        errores.append(f"El comentario admite hasta {MAX_COMENTARIO} caracteres.")
    turnos = {t for t in indisponible if t in turnos_validos()}
    if errores:
        return list(dict.fromkeys(errores))
    with transaccion():
        db = get_db()
        db.execute("DELETE FROM preferencia_oferta WHERE gestion_id = ? AND usuario_id = ?", [g["id"], uid])
        for aid, (nivel, nota) in materias.items():
            db.execute("""INSERT INTO preferencia_oferta (gestion_id, usuario_id, asignatura_id, nivel, nota)
                          VALUES (?, ?, ?, ?, ?)""", [g["id"], uid, aid, nivel, (nota or "").strip() or None])
        db.execute("""INSERT INTO preferencia_gestion (gestion_id, usuario_id, indisponible, comentario, actualizada_en)
                      VALUES (?, ?, ?, ?, datetime('now'))
                      ON CONFLICT (gestion_id, usuario_id) DO UPDATE SET indisponible = excluded.indisponible,
                          comentario = excluded.comentario, actualizada_en = excluded.actualizada_en""",
                   [g["id"], uid, ",".join(sorted(turnos)), (comentario or "").strip() or None])
        auditar(uid, "indicar_preferencias", "gestion_academica", g["id"],
                f"{gestiones.codigo(g)}: {len(materias)} materia(s), {len(turnos)} turno(s) sin disponibilidad")
    return []


def de_gestion(gid: int) -> list[dict]:
    """Lo que indicaron todos, para quien arma la oferta: una fila por persona con sus materias y turnos."""
    personas = get_db().q(
        """SELECT u.id, u.nombres, u.apellidos FROM usuario u WHERE u.id IN
              (SELECT usuario_id FROM preferencia_oferta WHERE gestion_id = ?
               UNION SELECT usuario_id FROM preferencia_gestion WHERE gestion_id = ?)
           ORDER BY u.apellidos, u.nombres""", [gid, gid])
    for p in personas:
        d = de_persona(gid, p["id"])
        p["indisponible"], p["comentario"] = sorted(d["indisponible"]), d["comentario"]
        p["materias"] = get_db().q(
            """SELECT a.sigla, a.nombre, f.nivel, f.nota FROM preferencia_oferta f JOIN asignatura a ON a.id = f.asignatura_id
               WHERE f.gestion_id = ? AND f.usuario_id = ? ORDER BY f.nivel DESC, a.sigla""", [gid, p["id"]])
    return personas


def sin_indicar(gid: int) -> list[dict]:
    """Docentes con vínculo al inicio de la gestión que aún no indicaron nada (para recordarles)."""
    g = gestiones.obtener(gid)
    return [p for p in get_db().q("SELECT id, nombres, apellidos FROM usuario WHERE activo = 1 ORDER BY apellidos, nombres")
            if vinculos.vigente(p["id"], g["fecha_inicio"]) and not tiene(gid, p["id"])]


def por_asignatura(gid: int, asignatura_id: int) -> dict[int, str]:
    """{usuario_id: nivel} de quienes indicaron algo sobre la asignatura (para ordenar y marcar el selector de docentes)."""
    return {f["usuario_id"]: f["nivel"] for f in get_db().q(
        "SELECT usuario_id, nivel FROM preferencia_oferta WHERE gestion_id = ? AND asignatura_id = ?", [gid, asignatura_id])}


def texto_turnos(turnos) -> str:
    """['lun-manana', 'lun-tarde', 'mar-noche'] → «lunes: mañana y tarde; martes: noche»."""
    por_dia: dict[str, list[str]] = {}
    for t in sorted(turnos, key=lambda x: (list(DIAS).index(x.split("-")[0]), list(TURNOS).index(x.split("-")[1]))):
        d, h = t.split("-")
        por_dia.setdefault(d, []).append(TURNOS[h].lower())
    return "; ".join(f"{DIAS[d].lower()}: {' y '.join(h)}" for d, h in por_dia.items())
