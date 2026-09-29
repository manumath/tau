"""Centro de avisos (PLAN.md, sección 33).

Cada aviso del sistema (propuestas por revisar, decisiones, carga en proyectos, continuidad…) se
guarda para su destinatario: lo ve en la campana de la barra y en la página «Avisos». Además, según su
preferencia (`usuario.frecuencia_avisos`), se le envía por correo al momento, en un resumen semanal o
no se le envía. Quien hace la acción no se avisa a sí mismo (lo decide quien llama).
"""
from datetime import datetime, timedelta

from app.comun import config, correo
from app.comun.db import AHORA, get_db

FRECUENCIAS = {"inmediato": "Por correo, al momento", "semanal": "Por correo, en un resumen semanal",
               "nunca": "Solo en el sistema (sin correo)"}
DIAS_RESUMEN = 7


def _enlace(url: str | None) -> str:
    return f"{config.URL_BASE}{url}" if url else config.URL_BASE


def avisar(u: dict | None, asunto: str, texto: str, url: str | None = None, cuerpo_correo: str | None = None):
    """Registra el aviso para `u` y, si lo prefiere así, se lo envía por correo ahora mismo."""
    if not u or not u.get("activo", 1):
        return
    get_db().t.notificacion.insert(usuario_id=u["id"], asunto=asunto, texto=texto, url=url)
    if u.get("frecuencia_avisos", "inmediato") == "inmediato":
        correo.enviar(u["email"], asunto,
                      f"Hola, {u['nombres']}:\n\n{cuerpo_correo or texto}\n\n{_enlace(url)}\n\n"
                      f"(Elija cómo recibir los avisos en {config.URL_BASE}/avisos)")


def no_leidas(uid: int) -> int:
    return get_db().q("SELECT COUNT(*) n FROM notificacion WHERE usuario_id = ? AND leida_en IS NULL", [uid])[0]["n"]


def recientes(uid: int, limite: int = 10) -> list[dict]:
    return get_db().q("""SELECT * FROM notificacion WHERE usuario_id = ?
                         ORDER BY leida_en IS NOT NULL, creada_en DESC, id DESC LIMIT ?""", [uid, limite])


def todas(uid: int, limite: int = 200) -> list[dict]:
    return get_db().q("SELECT * FROM notificacion WHERE usuario_id = ? ORDER BY creada_en DESC, id DESC LIMIT ?",
                      [uid, limite])


def abrir(nid: int, uid: int) -> dict | None:
    """Marca como leída una notificación propia y la devuelve (None si no es suya)."""
    filas = get_db().q("SELECT * FROM notificacion WHERE id = ? AND usuario_id = ?", [nid, uid])
    if filas and not filas[0]["leida_en"]:
        get_db().execute(f"UPDATE notificacion SET leida_en = {AHORA} WHERE id = ?", [nid])
    return filas[0] if filas else None


def marcar_todas(uid: int) -> int:
    n = no_leidas(uid)
    get_db().execute(f"UPDATE notificacion SET leida_en = {AHORA} WHERE usuario_id = ? AND leida_en IS NULL", [uid])
    return n


def fijar_frecuencia(uid: int, frecuencia: str) -> bool:
    if frecuencia not in FRECUENCIAS:
        return False
    get_db().execute("UPDATE usuario SET frecuencia_avisos = ? WHERE id = ?", [frecuencia, uid])
    return True


def resumen_semanal(ahora: datetime | None = None) -> int:
    """Envía el resumen a quien lo prefiere, si pasaron 7 días desde el anterior y hay avisos sin leer
    que aún no se resumieron. → cuántos correos envió."""
    ahora = ahora or datetime.now()
    limite = (ahora - timedelta(days=DIAS_RESUMEN)).isoformat(sep=" ", timespec="seconds")
    enviados = 0
    for u in get_db().q("""SELECT * FROM usuario WHERE activo = 1 AND frecuencia_avisos = 'semanal'
                           AND (ultimo_resumen IS NULL OR ultimo_resumen <= ?)""", [limite]):
        pendientes = get_db().q("""SELECT * FROM notificacion WHERE usuario_id = ? AND leida_en IS NULL
                                   AND resumida_en IS NULL ORDER BY creada_en""", [u["id"]])
        if not pendientes:
            continue
        lineas = "\n".join(f"- {n['asunto']}\n  {_enlace(n['url'])}" for n in pendientes)
        correo.enviar(u["email"], f"Resumen semanal de avisos ({len(pendientes)})",
                      f"Hola, {u['nombres']}:\n\nTiene {len(pendientes)} aviso(s) sin leer en {config.NOMBRE_SISTEMA}:"
                      f"\n\n{lineas}\n\nTodos sus avisos: {config.URL_BASE}/avisos")
        get_db().execute(f"""UPDATE notificacion SET resumida_en = {AHORA} WHERE usuario_id = ?
                             AND leida_en IS NULL AND resumida_en IS NULL""", [u["id"]])
        get_db().execute("UPDATE usuario SET ultimo_resumen = ? WHERE id = ?",
                         [ahora.isoformat(sep=" ", timespec="seconds"), u["id"]])
        enviados += 1
    return enviados
