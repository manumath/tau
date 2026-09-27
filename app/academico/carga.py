"""Carga horaria semestral (PLAN.md, sección 24, paso 3.4).

- La carga se cuenta en unidades de 32 h/mes. Cada persona tiene **una** carga contratada por
  semestre (I o II): 32, 64, 96, 128 o 160 h/mes (160 = tiempo completo).
- La Dirección de Carrera la distribuye:
  - docencia: 32 h/mes por materia asignada como titular (grado o maestría), calculada de la oferta;
  - investigación, extensión, gestión y otras: múltiplos de 32 h/mes, con un detalle.
- No suman: los auxiliares ni los cursos de verano e invierno (cuentan como docencia dictada).
- La distribución debe sumar la carga contratada; si no, se avisa.
- Jornada completa equivalente (anexo de acreditación) = carga contratada / 160.
"""
from app.academico import oferta
from app.comun.db import AHORA, get_db, transaccion

UNIDAD = 32
CARGAS = (32, 64, 96, 128, 160)
TIEMPO_COMPLETO = 160
TIPOS = {"investigacion": "Investigación", "extension": "Extensión y servicios", "gestion": "Gestión",
         "otras": "Otras"}
SEMESTRES = ("I", "II")


def obtener(usuario_id: int, gestion_id: int) -> dict | None:
    filas = get_db().q("SELECT * FROM carga_semestral WHERE usuario_id = ? AND gestion_id = ?", [usuario_id, gestion_id])
    return filas[0] if filas else None


def actividades(carga_id: int) -> list[dict]:
    return get_db().q("SELECT * FROM carga_actividad WHERE carga_id = ? ORDER BY tipo, id", [carga_id])


def resumen(usuario_id: int, gestion: dict) -> dict:
    """Carga contratada, docencia, actividades, horas por tipo, total y avisos de la persona."""
    c = obtener(usuario_id, gestion["id"])
    materias = oferta.materias_de(usuario_id, gestion["id"])
    docencia = oferta.horas_de_docencia(usuario_id, gestion["id"])
    acts = actividades(c["id"]) if c else []
    por_tipo = {t: sum(a["horas"] for a in acts if a["tipo"] == t) for t in TIPOS}
    total = docencia + sum(por_tipo.values())
    contratada = c["horas_contratadas"] if c else None
    avisos = []
    if contratada is None:
        if total:
            avisos.append("Falta registrar la carga contratada del semestre.")
    elif total < contratada:
        avisos.append(f"Faltan {contratada - total} h/mes por asignar.")
    elif total > contratada:
        avisos.append(f"La distribución supera la carga contratada en {total - contratada} h/mes.")
    if total > TIEMPO_COMPLETO:
        avisos.append(f"El total ({total} h/mes) supera el tiempo completo ({TIEMPO_COMPLETO} h/mes).")
    return {"carga": c, "contratada": contratada, "materias": materias, "docencia": docencia, "actividades": acts,
            "por_tipo": por_tipo, "total": total, "avisos": avisos}


def personas(gestion: dict) -> list[dict]:
    """Quienes tienen carga registrada o dictan como titulares en el semestre (con su resumen)."""
    ids = [f["usuario_id"] for f in get_db().q(
        """SELECT usuario_id FROM carga_semestral WHERE gestion_id = :g
           UNION SELECT d.usuario_id FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
                 WHERE o.gestion_id = :g AND d.rol = 'titular'""", {"g": gestion["id"]})]
    res = []
    for p in get_db().q(f"""SELECT id, nombres, apellidos FROM usuario WHERE id IN ({",".join("?" * len(ids)) or "NULL"})
                            ORDER BY apellidos, nombres""", ids):
        res.append({**p, **resumen(p["id"], gestion)})
    return res


def _validar_semestre(gestion: dict) -> str | None:
    if gestion["tipo"] not in SEMESTRES:
        return "La carga horaria se asigna por semestre (I o II); los cursos de temporada no forman parte de ella."
    return None


def fijar_contratada(usuario_id: int, gestion: dict, horas, por: int) -> str | None:
    if (e := _validar_semestre(gestion)):
        return e
    h = int(horas) if str(horas).isdigit() else None
    if h not in CARGAS:
        return "La carga contratada es de 32, 64, 96, 128 o 160 h/mes."
    get_db().execute(f"""INSERT INTO carga_semestral (usuario_id, gestion_id, horas_contratadas, registrada_por)
                         VALUES (?, ?, ?, ?)
                         ON CONFLICT (usuario_id, gestion_id) DO UPDATE SET horas_contratadas = excluded.horas_contratadas,
                         registrada_por = excluded.registrada_por, actualizado_en = {AHORA}""",
                     [usuario_id, gestion["id"], h, por])
    return None


def agregar_actividad(usuario_id: int, gestion: dict, tipo: str, horas, detalle: str) -> str | None:
    if (e := _validar_semestre(gestion)):
        return e
    c = obtener(usuario_id, gestion["id"])
    if not c:
        return "Registre primero la carga contratada del semestre."
    if tipo not in TIPOS:
        return "Elija el tipo de actividad."
    h = int(horas) if str(horas).isdigit() else None
    if not h or h % UNIDAD or not UNIDAD <= h <= TIEMPO_COMPLETO:
        return "Las horas son múltiplos de 32 h/mes (32, 64, 96…)."
    detalle = (detalle or "").strip()[:300] or None
    get_db().t.carga_actividad.insert(carga_id=c["id"], tipo=tipo, horas=h, detalle=detalle)
    return None


def quitar_actividad(aid: int) -> dict | None:
    filas = get_db().q("""SELECT a.*, c.usuario_id, c.gestion_id FROM carga_actividad a
                          JOIN carga_semestral c ON c.id = a.carga_id WHERE a.id = ?""", [aid])
    if filas:
        get_db().execute("DELETE FROM carga_actividad WHERE id = ?", [aid])
    return filas[0] if filas else None


def anterior(gestion: dict) -> dict | None:
    """El semestre anterior (I-2026 → II-2025; II-2026 → I-2026)."""
    anio, tipo = (gestion["anio"] - 1, "II") if gestion["tipo"] == "I" else (gestion["anio"], "I")
    filas = get_db().q("SELECT * FROM gestion_academica WHERE anio = ? AND tipo = ?", [anio, tipo])
    return filas[0] if filas else None


def copiar_del_anterior(gestion: dict, por: int) -> int:
    """Copia carga contratada y actividades de quienes no tienen carga en este semestre (útil para
    los titulares, cuya carga suele repetirse). La docencia no se copia: sale de la oferta. → cuántas."""
    previo = anterior(gestion)
    if not previo or _validar_semestre(gestion):
        return 0
    n = 0
    with transaccion():
        for c in get_db().q("SELECT * FROM carga_semestral WHERE gestion_id = ?", [previo["id"]]):
            if obtener(c["usuario_id"], gestion["id"]):
                continue
            nueva = get_db().t.carga_semestral.insert(usuario_id=c["usuario_id"], gestion_id=gestion["id"],
                                                      horas_contratadas=c["horas_contratadas"], registrada_por=por)["id"]
            for a in actividades(c["id"]):
                get_db().t.carga_actividad.insert(carga_id=nueva, tipo=a["tipo"], horas=a["horas"], detalle=a["detalle"])
            n += 1
    return n


def contratada_en(usuario_id: int, fecha: str) -> int | None:
    """Carga contratada (h/mes) del semestre que cubre la fecha o, si no hay, del último anterior."""
    filas = get_db().q(
        """SELECT c.horas_contratadas FROM carga_semestral c JOIN gestion_academica g ON g.id = c.gestion_id
           WHERE c.usuario_id = ? AND g.fecha_inicio <= ? ORDER BY g.fecha_inicio DESC LIMIT 1""", [usuario_id, fecha])
    return filas[0]["horas_contratadas"] if filas else None
