"""Ciclo de vida de un semestre o curso de temporada: activarlo, concluirlo y reabrirlo (PLAN §66).

planificación → activa → concluida (historial). Activar, concluir y reabrir son de la Dirección de Carrera
(`decidir_gestion`); las rutas lo comprueban. Para activar, la lista de verificación de la planificación
(`app.academico.preparacion`) no puede tener puntos que lo impidan: la oferta cargada y un titular en cada paralelo.
Contratos por renovar y carga con observaciones solo avisan.
"""
from datetime import date

from app.academico import gestiones, preparacion
from app.comun.db import AHORA, auditar, get_db, transaccion

IMPIDEN = ("oferta", "docentes")      # etapas de la preparación que impiden activar


def _etapas(g: dict) -> list[dict]:
    return preparacion.estado(g["anio"], g["tipo"])["etapas"]


def bloqueos(g: dict) -> list[str]:
    """Lo que impide activar la gestión (vacío: se puede)."""
    res = []
    etapas = {e["clave"]: e for e in _etapas(g)}
    if not etapas["oferta"]["listo"]:
        res.append("Falta cargar la oferta del semestre.")
    elif not etapas["docentes"]["listo"]:
        res.append(f"Falta {etapas['docentes']['falta']}.")
    return res


def avisos(g: dict) -> list[str]:
    """Lo que conviene revisar antes de activar, pero no lo impide."""
    return [f"{e['titulo']}: {e['detalle']}." for e in _etapas(g)
            if e["clave"] not in IMPIDEN and e["clave"] != "gestion" and not e["listo"]]


def activar(gid: int, uid: int) -> list[str]:
    g = gestiones.obtener(gid)
    if not g or g["estado"] != "planificacion":
        return ["Solo se activa una gestión en planificación."]
    falta = bloqueos(g)
    if falta:
        return falta
    with transaccion():
        get_db().execute(f"UPDATE gestion_academica SET estado = 'activa', activada_en = {AHORA}, activada_por = ? "
                         "WHERE id = ?", [uid, gid])
        auditar(uid, "activar_gestion", "gestion_academica", gid, gestiones.codigo(g))
    return []


def concluir(gid: int, motivo: str, uid: int) -> list[str]:
    """Pasa una gestión activa al historial. Antes de su término solo se concluye con motivo (cierre anticipado)."""
    g = gestiones.obtener(gid)
    if not g or g["estado"] != "activa":
        return ["Solo se concluye una gestión activa."]
    motivo = (motivo or "").strip()
    anticipado = g["fecha_fin"] >= date.today().isoformat()
    if anticipado and not motivo:
        return [f"{gestiones.codigo(g)} termina el {g['fecha_fin']}: para concluirla antes, indique el motivo."]
    if len(motivo) > 500:
        return ["El motivo admite hasta 500 caracteres."]
    with transaccion():
        get_db().execute(f"UPDATE gestion_academica SET estado = 'concluida', concluida_en = {AHORA}, concluida_por = ?, "
                         "motivo_conclusion = ? WHERE id = ?", [uid, motivo or None, gid])
        auditar(uid, "concluir_gestion", "gestion_academica", gid,
                gestiones.codigo(g) + (f" (antes de su término: {motivo})" if anticipado else ""))
    return []


def reabrir(gid: int, motivo: str, uid: int) -> list[str]:
    """Devuelve una gestión concluida a «activa» para corregirla; exige el motivo."""
    g = gestiones.obtener(gid)
    if not g or g["estado"] != "concluida":
        return ["Solo se reabre una gestión concluida."]
    motivo = (motivo or "").strip()
    if not motivo or len(motivo) > 500:
        return ["Indique por qué se reabre (hasta 500 caracteres)."]
    with transaccion():
        get_db().execute("UPDATE gestion_academica SET estado = 'activa', concluida_en = NULL, concluida_por = NULL, "
                         "motivo_conclusion = NULL WHERE id = ?", [gid])
        auditar(uid, "reabrir_gestion", "gestion_academica", gid, f"{gestiones.codigo(g)}: {motivo}")
    return []
