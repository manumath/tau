"""«Mis pendientes» y «Mi calendario» del docente (PLAN §68, etapa 1). No guardan nada y son solo de la propia persona.

Cada módulo activo aporta lo suyo (grado, auxiliaturas, tutoría, temas, eventos, plan de mejora; PLAN §73, etapa 3) y aquí
está lo de la docencia: el vínculo, las preferencias, los programas y las fechas de los semestres (`aporte_pendientes` y
`aporte_eventos`, que declara el módulo de oferta). Formato de pendientes y eventos: `app/comun/calendario.py`."""
from datetime import date, timedelta

from app.academico import gestiones
from app.comun import calendario, vinculos
from app.comun.calendario import evento as _evento, pendiente as _pendiente
from app.comun.db import get_db

TIPOS = {"grado": "Grado", "auxiliatura": "Auxiliaturas", "tutoria": "Tutoría", "tema": "Temas de grado",
         "vinculo": "Vínculo", "preferencias": "Oferta", "programa": "Programa", "gestion": "Semestre", "evento": "Evento",
         "mejora": "Plan de mejora"}
DIAS_VINCULO = 60       # avisa cuando el periodo del vínculo termina en menos de estos días


def es_docente(auth: dict | None) -> bool:
    """¿Tiene algo que hacer como docente? Vínculo, materias, tutorías, temas, tribunales o trámites de grado."""
    if not auth or auth.get("solo_estudiante"):
        return False
    return bool(get_db().q(
        """SELECT 1 FROM vinculo WHERE usuario_id = :u UNION SELECT 1 FROM oferta_docente WHERE usuario_id = :u
           UNION SELECT 1 FROM tutoria_asignacion WHERE tutor_id = :u UNION SELECT 1 FROM tema_grado WHERE docente_id = :u
           UNION SELECT 1 FROM tramite_grado WHERE tutor_id = :u UNION SELECT 1 FROM tribunal_grado WHERE usuario_id = :u
           UNION SELECT 1 FROM tribunal_auxiliatura WHERE usuario_id = :u LIMIT 1""", {"u": auth["id"]}))


# --- Pendientes ---------------------------------------------------------------------------------------------------------

def _vinculo(uid: int, hoy: date):
    v = vinculos.vigente(uid)
    if v and v["fecha_fin"] and hoy <= date.fromisoformat(v["fecha_fin"]) <= hoy + timedelta(days=DIAS_VINCULO):
        yield _pendiente("vinculo", "Su periodo de vínculo termina", vinculos.CATEGORIAS[v["categoria"]], v["fecha_fin"],
                         "/docencia/mia")


def _preferencias(uid: int):
    """El próximo semestre (I o II) en planificación para el que aún no indicó preferencias (solo si puede indicarlas). Los cursos
    de temporada no se piden aquí: los dictan solo titulares y se arman aparte."""
    from app.academico import preferencias
    g = next((x for x in preferencias.gestiones_abiertas() if x["tipo"] in ("I", "II")), None)
    if g and preferencias.puede_indicar(uid, g) is None and not preferencias.tiene(g["id"], uid):
        yield _pendiente("preferencias", f"Indique sus preferencias para {gestiones.codigo(g)}",
                         "Materias que prefiere y turnos sin disponibilidad", g["fecha_inicio"],
                         f"/docencia/preferencias?gestion={g['id']}")


def _programas(uid: int):
    from app.academico import programas
    for m in programas.pendientes_de(uid):
        yield _pendiente("programa", f"Publique el programa de {m['sigla']}", f"{m['nombre']} · {m['gestion']}",
                         m["fecha_inicio"], f"/docencia/programas/{m['asignatura_id']}/{m['gestion_id']}")


def aporte_pendientes(ambito: str, uid: int, hoy: date):
    """Lo de la docencia en «Mis pendientes» del docente."""
    if ambito != "docente":
        return []
    return [*_preferencias(uid), *_programas(uid), *_vinculo(uid, hoy)]


def pendientes(uid: int, hoy: date | None = None) -> list[dict]:
    """Lo que la persona debe hacer, lo que vence antes primero (y lo que no tiene fecha, después)."""
    return calendario.pendientes_de("docente", uid, hoy)


def situacion(p: dict, hoy: date | None = None) -> str:
    """'vencido', 'proximo' (en los próximos 7 días) o 'normal'."""
    return calendario.situacion(p, hoy)


# --- Calendario -----------------------------------------------------------------------------------------------------

def _eventos_gestiones(href: str | None):
    for g in gestiones.listar():
        yield _evento(g["fecha_inicio"], f"Inicia {gestiones.codigo(g)}", "gestion", gestiones.nombre(g), href)
        yield _evento(g["fecha_fin"], f"Termina {gestiones.codigo(g)}", "gestion", gestiones.nombre(g), href)


def _eventos_vinculo(uid: int):
    v = vinculos.vigente(uid)
    if v and v["fecha_fin"]:
        yield _evento(v["fecha_fin"], "Termina su periodo de vínculo", "vinculo", vinculos.CATEGORIAS[v["categoria"]], "/docencia/mia")


def aporte_eventos(ambito: str, quien: int, desde: date, hasta: date):
    """Las fechas de los semestres (para el docente y para el estudiante) y el término del vínculo del docente."""
    if ambito == "docente":
        return [*_eventos_gestiones("/docencia/mia"), *_eventos_vinculo(quien)]
    return list(_eventos_gestiones(None)) if ambito == "estudiante" else []


def eventos(uid: int, desde: date | None = None, hasta: date | None = None) -> list[dict]:
    """Las fechas de la persona entre `desde` y `hasta` (por omisión, de hoy a 120 días), en orden."""
    return calendario.eventos_de("docente", uid, desde, hasta)
