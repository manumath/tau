"""Calendario académico del estudiante (PLAN §67, etapa 2): sus fechas en un solo lugar. No guarda nada: reúne lo que otros
módulos ya tienen (gestiones, convocatorias, defensas, eventos) y, en las etapas siguientes, becas, reuniones de tutoría y
demás. Cada evento: {fecha, hora, titulo, tipo, detalle, href}."""
from datetime import date, timedelta

from app.academico import gestiones
from app.comun import estudiantes
from app.comun.db import get_db

TIPOS = {"gestion": "Semestre", "evento": "Evento", "auxiliatura": "Auxiliaturas", "grado": "Grado", "oportunidad": "Oportunidad",
         "tutoria": "Tutoría", "encuesta": "Encuesta"}


def _evento(iso: str | None, titulo: str, tipo: str, detalle: str = "", href: str | None = None) -> dict | None:
    if not iso:
        return None
    return {"fecha": iso[:10], "hora": iso[11:16] if len(iso) >= 16 else "", "titulo": titulo, "tipo": tipo,
            "detalle": detalle, "href": href}


def _gestiones(desde: str, hasta: str):
    for g in gestiones.listar():
        n = gestiones.nombre(g)
        yield _evento(g["fecha_inicio"], f"Inicia {gestiones.codigo(g)}", "gestion", n)
        yield _evento(g["fecha_fin"], f"Termina {gestiones.codigo(g)}", "gestion", n)


def _auxiliaturas(desde: str, hasta: str):
    for c in get_db().q("SELECT * FROM convocatoria_auxiliatura WHERE estado = 'publicada'"):
        yield _evento(c["cierre"], f"Cierra la recepción: {c['titulo']}", "auxiliatura", c["lugar"] or "",
                      "/estudiante/auxiliaturas")
        yield _evento(c["examen"], f"Examen escrito: {c['titulo']}", "auxiliatura", c["lugar"] or "",
                      "/estudiante/auxiliaturas")


def _grado(externo_id: int, desde: str, hasta: str):
    from app.servicios import grado
    for t in grado.de_estudiante(externo_id):
        tipo = grado.TIPOS[t["tipo"]]
        href = f"/estudiante/grado/{t['id']}"
        if t["estado"] == "en_revision":
            yield _evento(t["plazo"], f"Vence la revisión del tribunal ({tipo.lower()})", "grado", t["titulo"], href)
        yield _evento(t.get("reunion_en"), f"Reunión con el tribunal: {t['titulo']}", "grado", "", href)
        yield _evento(t.get("defensa_en"), f"Defensa: {t['titulo']}", "grado", "", href)


def _tutoria(externo_id: int, desde: str, hasta: str):
    for s in get_db().q("SELECT * FROM tutoria_solicitud WHERE externo_id = ? AND estado = 'programada'", [externo_id]):
        yield _evento(s["fecha_reunion"], "Reunión con su tutor(a)", "tutoria", s["respuesta"] or "", "/estudiante/tutoria")


def _oportunidades(externo_id: int, desde: str, hasta: str):
    from app.servicios import oportunidades
    for o in oportunidades.para_estudiante(externo_id):
        yield _evento(o["cierre"], f"Cierra: {o['titulo']}", "oportunidad", oportunidades.TIPOS[o["tipo"]],
                      f"/estudiante/oportunidades/{o['id']}")


def _encuestas(externo_id: int, desde: str, hasta: str):
    from app.estudiantil import encuestas
    for e in encuestas.por_responder(externo_id):
        yield _evento(e["cierra_el"], f"Cierra la encuesta: {e['titulo']}", "encuesta", "", f"/encuesta/{e['token']}")


def _eventos(uid: int, desde: str, hasta: str):
    for c in get_db().q(
            """SELECT c.* FROM comunicado c WHERE c.tipo = 'evento' AND c.estado = 'publicado' AND c.inicio IS NOT NULL
               AND (c.para_todos = 1 OR EXISTS (SELECT 1 FROM comunicado_destinatario d WHERE d.comunicado_id = c.id
                                                AND d.usuario_id = ?))""", [uid]):
        yield _evento(c["inicio"], c["titulo"], "evento", c["lugar"] or "", f"/estudiante/comunicados/{c['id']}")


def eventos(externo_id: int, desde: date | None = None, hasta: date | None = None) -> list[dict]:
    """Las fechas del estudiante entre `desde` y `hasta` (por omisión, de hoy a 120 días), en orden."""
    desde = desde or date.today()
    hasta = hasta or desde + timedelta(days=120)
    d, h = desde.isoformat(), hasta.isoformat()
    usuario = estudiantes.usuario_de(externo_id)
    uid = usuario["id"] if usuario else 0
    todos = [e for fuente in (_gestiones(d, h), _auxiliaturas(d, h), _grado(externo_id, d, h), _eventos(uid, d, h),
                    _tutoria(externo_id, d, h), _oportunidades(externo_id, d, h), _encuestas(externo_id, d, h))
             for e in fuente if e]
    return sorted((e for e in todos if d <= e["fecha"] <= h), key=lambda e: (e["fecha"], e["hora"], e["titulo"]))


def _ics(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace(";", r"\;").replace(",", "\\,").replace("\n", "\\n")


def ics(lista: list[dict], nombre: str = "TAU") -> str:
    """Los eventos como archivo de calendario (.ics) para Google Calendar, Outlook o el teléfono."""
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{nombre}//Calendario del estudiante//ES", "CALSCALE:GREGORIAN"]
    for n, e in enumerate(lista):
        f = e["fecha"].replace("-", "")
        inicio = f"DTSTART:{f}T{e['hora'].replace(':', '')}00" if e["hora"] else f"DTSTART;VALUE=DATE:{f}"
        lineas += ["BEGIN:VEVENT", f"UID:{f}-{n}-{abs(hash(e['titulo'])) % 10**8}@tau", f"DTSTAMP:{date.today():%Y%m%d}T000000Z",
                   inicio, f"SUMMARY:{_ics(e['titulo'])}"]
        if e["detalle"]:
            lineas.append(f"DESCRIPTION:{_ics(e['detalle'])}")
        lineas.append("END:VEVENT")
    lineas.append("END:VCALENDAR")
    return "\r\n".join(lineas) + "\r\n"
