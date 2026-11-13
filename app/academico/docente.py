"""«Mis pendientes» y «Mi calendario» del docente (PLAN §68, etapa 1). No guardan nada: reúnen lo que otros módulos ya
tienen (grado, auxiliaturas, tutoría, temas, vínculo, gestiones, eventos) y solo de la propia persona.

Pendiente: {tipo, titulo, detalle, cuando (ISO o None), href}. Evento: {fecha, hora, titulo, tipo, detalle, href}."""
from datetime import date, timedelta

from app.academico import gestiones
from app.comun import vinculos
from app.comun.db import get_db

TIPOS = {"grado": "Grado", "auxiliatura": "Auxiliaturas", "tutoria": "Tutoría", "tema": "Temas de grado",
         "vinculo": "Vínculo", "preferencias": "Oferta", "programa": "Programa", "gestion": "Semestre", "evento": "Evento"}
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


def _pendiente(tipo: str, titulo: str, detalle: str = "", cuando: str | None = None, href: str | None = None) -> dict:
    return {"tipo": tipo, "titulo": titulo, "detalle": detalle, "cuando": (cuando or None) and cuando[:10], "href": href}


# --- Pendientes ---------------------------------------------------------------------------------------------------------

def _grado(uid: int):
    from app.servicios import grado
    for t in grado.de_tutor(uid):
        if t["estado"] == "con_tutor":
            yield _pendiente("grado", f"Su visto bueno: {t['nombres']} {t['apellidos']}",
                             f"{grado.TIPOS[t['tipo']]} «{t['titulo']}»", None, grado.url_staff(t))
    for t in grado.pendientes_de(uid):
        yield _pendiente("grado", f"{t['que']}: {t['nombres']} {t['apellidos']}",
                         f"{grado.TIPOS[t['tipo']]} «{t['titulo']}»", t["cuando"], grado.url_staff(t))


def _auxiliaturas(uid: int):
    from app.servicios import auxiliaturas
    for i in auxiliaturas.items_de_miembro(uid):
        if i["por_calificar"]:
            yield _pendiente("auxiliatura", f"Calificar {i['por_calificar']} postulante(s)", i["convocatoria"], None,
                             auxiliaturas.url_miembro(uid, i["id"]))


def _tutoria(uid: int):
    from app.estudiantil import tutoria
    for s in tutoria.solicitudes_abiertas_de_tutor(uid):
        if s["estado"] == "pendiente":
            yield _pendiente("tutoria", f"Reunión que pide {s['nombres']} {s['apellidos']}", (s["mensaje"] or "")[:120],
                             None, f"/tutoria/{s['externo_id']}")


def _temas(uid: int):
    for s in get_db().q(
            """SELECT s.id, t.id AS tema_id, t.titulo, pe.nombres, pe.apellidos FROM solicitud_tema s
               JOIN tema_grado t ON t.id = s.tema_id JOIN persona_externa pe ON pe.id = s.externo_id
               WHERE t.docente_id = ? AND s.estado = 'pendiente' ORDER BY s.id""", [uid]):
        yield _pendiente("tema", f"Pide su tutoría: {s['nombres']} {s['apellidos']}", f"Tema «{s['titulo']}»", None,
                         f"/servicios/temas/{s['tema_id']}")


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


FUENTES_PENDIENTES = (_grado, _auxiliaturas, _tutoria, _temas, _preferencias, _programas)


def pendientes(uid: int, hoy: date | None = None) -> list[dict]:
    """Lo que la persona debe hacer, lo que vence antes primero (y lo que no tiene fecha, después)."""
    hoy = hoy or date.today()
    todos = [p for f in FUENTES_PENDIENTES for p in f(uid)] + list(_vinculo(uid, hoy))
    return sorted(todos, key=lambda p: (p["cuando"] is None, p["cuando"] or "", p["titulo"]))


def situacion(p: dict, hoy: date | None = None) -> str:
    """'vencido', 'proximo' (en los próximos 7 días) o 'normal'."""
    if not p["cuando"]:
        return "normal"
    d = date.fromisoformat(p["cuando"]) - (hoy or date.today())
    return "vencido" if d.days < 0 else "proximo" if d.days <= 7 else "normal"


# --- Calendario -----------------------------------------------------------------------------------------------------

def _evento(iso: str | None, titulo: str, tipo: str, detalle: str = "", href: str | None = None) -> dict | None:
    if not iso:
        return None
    return {"fecha": iso[:10], "hora": iso[11:16] if len(iso) >= 16 else "", "titulo": titulo, "tipo": tipo,
            "detalle": detalle, "href": href}


def _eventos_gestiones():
    for g in gestiones.listar():
        yield _evento(g["fecha_inicio"], f"Inicia {gestiones.codigo(g)}", "gestion", gestiones.nombre(g), "/docencia/mia")
        yield _evento(g["fecha_fin"], f"Termina {gestiones.codigo(g)}", "gestion", gestiones.nombre(g), "/docencia/mia")


def _eventos_grado(uid: int):
    from app.servicios import grado
    vistos = set()
    for t in [*grado.de_tutor(uid), *grado.de_miembro(uid)]:
        if t["id"] in vistos:
            continue
        vistos.add(t["id"])
        href, quien = grado.url_staff(t), f"{t['nombres']} {t['apellidos']}"
        if t["estado"] == "en_revision":
            yield _evento(t["plazo"], f"Vence la revisión del tribunal: {quien}", "grado", t["titulo"], href)
        yield _evento(t.get("reunion_en"), f"Reunión con el tribunal: {quien}", "grado", t["titulo"], href)
        yield _evento(t.get("defensa_en"), f"Defensa: {quien}", "grado", t["titulo"], href)


def _eventos_tutoria(uid: int):
    from app.estudiantil import tutoria
    for s in tutoria.solicitudes_abiertas_de_tutor(uid):
        if s["estado"] == "programada":
            yield _evento(s["fecha_reunion"], f"Reunión con {s['nombres']} {s['apellidos']}", "tutoria", s["respuesta"] or "",
                          f"/tutoria/{s['externo_id']}")


def eventos_comunicados(uid: int):
    for c in get_db().q(
            """SELECT c.* FROM comunicado c WHERE c.tipo = 'evento' AND c.estado = 'publicado' AND c.inicio IS NOT NULL
               AND (c.para_todos = 1 OR EXISTS (SELECT 1 FROM comunicado_destinatario d WHERE d.comunicado_id = c.id
                                                AND d.usuario_id = ?))""", [uid]):
        yield _evento(c["inicio"], c["titulo"], "evento", c["lugar"] or "", "/avisos")


def _eventos_vinculo(uid: int):
    v = vinculos.vigente(uid)
    if v and v["fecha_fin"]:
        yield _evento(v["fecha_fin"], "Termina su periodo de vínculo", "vinculo", vinculos.CATEGORIAS[v["categoria"]], "/docencia/mia")


def eventos(uid: int, desde: date | None = None, hasta: date | None = None) -> list[dict]:
    """Las fechas de la persona entre `desde` y `hasta` (por omisión, de hoy a 120 días), en orden."""
    desde = desde or date.today()
    hasta = hasta or desde + timedelta(days=120)
    d, h = desde.isoformat(), hasta.isoformat()
    todos = [e for fuente in (_eventos_gestiones(), _eventos_grado(uid), _eventos_tutoria(uid), eventos_comunicados(uid),
                              _eventos_vinculo(uid)) for e in fuente if e]
    return sorted((e for e in todos if d <= e["fecha"] <= h), key=lambda e: (e["fecha"], e["hora"], e["titulo"]))
