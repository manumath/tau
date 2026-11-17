"""Piloto con usuarios reales (PLAN §72, etapa 9): comentarios sobre cada pantalla y adopción por rol y semana.

- **Comentarios:** solo con `TAU_PILOTO=1`. Se guarda el texto, la ruta sin parámetros (los números de la dirección se
  reemplazan por «:id», para que no identifiquen un registro), el rol y el día; no la cuenta, la hora ni los datos de la
  pantalla. La Administración del sistema los lista y los marca como atendidos.
- **Adopción:** cuántas personas entraron y cuántas registraron algo, por rol y semana, sacado de la auditoría que ya
  existe. Son conteos: no se muestran nombres.
"""
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from app.comun import estudiantes, permisos
from app.comun.db import get_db

MAX_TEXTO = 2000
SEMANAS = 8
# Acciones de la auditoría que no son «registrar algo»: entrar y consultar.
SOLO_CONSULTA = {"login", "login_enlace", "logout"}
PREFIJOS_CONSULTA = ("ver_", "exportar_", "consultar_")
SIN_ROL = "Docentes e investigadores"
ESTUDIANTES = "Estudiantes"


def ruta_sin_parametros(url: str) -> str:
    """«https://x/calidad/mejora/actividades/12?volver=…» → «/calidad/mejora/actividades/:id»."""
    ruta = urlsplit(url or "").path or "/"
    ruta = "/".join(":id" if re.fullmatch(r"\d+|[0-9a-f-]{16,}|[\w-]{24,}", p) else p for p in ruta.split("/"))
    return ruta[:200]


def roles_de(uid: int) -> list[str]:
    """Nombres de los roles vigentes; sin rol, «Estudiantes» si la cuenta es de estudiante o «Docentes e investigadores»."""
    nombres = sorted({permisos.ROLES[r["rol"]][0] for r in permisos.roles_vigentes(uid) if r["rol"] in permisos.ROLES})
    if nombres:
        return nombres
    return [ESTUDIANTES if estudiantes.cuenta_de(uid) else SIN_ROL]


def comentar(uid: int, url: str, texto: str) -> list[str]:
    texto = (texto or "").strip()
    if len(texto) < 3:
        return ["Escriba su comentario."]
    if len(texto) > MAX_TEXTO:
        return [f"El comentario no puede pasar de {MAX_TEXTO} caracteres."]
    get_db().t.comentario_piloto.insert(ruta=ruta_sin_parametros(url), rol=", ".join(roles_de(uid)), texto=texto)
    return []


def comentarios(pendientes: bool = True) -> list[dict]:
    donde = "WHERE atendido_en IS NULL" if pendientes else "WHERE atendido_en IS NOT NULL"
    return get_db().q(f"SELECT * FROM comentario_piloto {donde} ORDER BY dia DESC, id DESC LIMIT 500")


def conteo() -> dict:
    f = get_db().q("""SELECT SUM(atendido_en IS NULL) AS pendientes, SUM(atendido_en IS NOT NULL) AS atendidos
                      FROM comentario_piloto""")[0]
    return {"pendientes": f["pendientes"] or 0, "atendidos": f["atendidos"] or 0}


def atender(cid: int, uid: int, nota: str) -> bool:
    db = get_db()
    if not db.q("SELECT 1 FROM comentario_piloto WHERE id = ?", [cid]):
        return False
    db.t.comentario_piloto.update({"atendido_en": datetime.now().isoformat(timespec="seconds"), "atendido_por": uid,
                                   "nota": (nota or "").strip()[:1000] or None}, cid)
    return True


def reabrir(cid: int) -> bool:
    db = get_db()
    if not db.q("SELECT 1 FROM comentario_piloto WHERE id = ?", [cid]):
        return False
    db.t.comentario_piloto.update({"atendido_en": None, "atendido_por": None}, cid)
    return True


# --- Adopción -----------------------------------------------------------------------------------------------------------

def _dia_local(fecha_utc: str) -> date:
    """'2026-11-16 01:30:00' (UTC, como la guarda la auditoría) → el día de aquí (15 de noviembre en La Paz)."""
    momento = datetime.fromisoformat(fecha_utc)
    if len(fecha_utc) <= 10:   # solo fecha: no hay hora que convertir
        return momento.date()
    return momento.replace(tzinfo=timezone.utc).astimezone().date()


def _lunes(d: date) -> date:
    return d - timedelta(days=d.weekday())


def adopcion(hoy: date | None = None, semanas: int = SEMANAS) -> dict:
    """{"semanas": [lunes…], "filas": [{"rol", "entraron": [n…], "registraron": [n…]}]} de las últimas `semanas`.

    Una persona con dos roles cuenta en ambos. La auditoría guarda la fecha en UTC y las semanas son las de aquí: cada
    registro se pasa a la fecha local (si no, lo hecho un domingo por la noche caería en la semana siguiente)."""
    hoy = hoy or date.today()
    lunes = [_lunes(hoy) - timedelta(weeks=k) for k in range(semanas - 1, -1, -1)]
    # Un día de margen en la consulta: el corte exacto, ya en fecha local, lo hace `indice` más abajo.
    filas = get_db().q("SELECT usuario_id, accion, fecha FROM auditoria WHERE usuario_id IS NOT NULL AND fecha >= ?",
                       [(lunes[0] - timedelta(days=1)).isoformat()])
    indice = {lu: i for i, lu in enumerate(lunes)}
    entraron: dict[str, list[set]] = {}
    registraron: dict[str, list[set]] = {}
    roles: dict[int, list[str]] = {}
    for f in filas:
        i = indice.get(_lunes(_dia_local(f["fecha"])))
        if i is None:
            continue
        uid = f["usuario_id"]
        if uid not in roles:
            roles[uid] = roles_de(uid)
        consulta = f["accion"] in SOLO_CONSULTA or f["accion"].startswith(PREFIJOS_CONSULTA)
        for r in roles[uid]:
            entraron.setdefault(r, [set() for _ in lunes])[i].add(uid)
            if not consulta:
                registraron.setdefault(r, [set() for _ in lunes])[i].add(uid)
    vacio = [set() for _ in lunes]
    return {"semanas": lunes,
            "filas": [{"rol": r, "entraron": [len(s) for s in entraron[r]],
                       "registraron": [len(s) for s in registraron.get(r, vacio)]} for r in sorted(entraron)]}
