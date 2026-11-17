"""Pendientes y fechas de una persona (PLAN §68, §69 y §73): las piezas que comparten «Mis pendientes» y «Mi calendario» del
docente, del investigador y del estudiante. Cada módulo aporta los suyos (`pendientes` y `eventos` en su `aportes.py`) y
las pantallas juntan los de los módulos activos con `pendientes_de` y `eventos_de`. No se guarda nada.

Pendiente: {tipo, titulo, detalle, cuando (ISO o None), href}. Evento: {fecha, hora, titulo, tipo, detalle, href}.
Ámbitos: «docente» e «investigador» (la persona es un `usuario.id`) y «estudiante» (es su ficha, `persona_externa.id`)."""
from datetime import date, timedelta

from app.comun import modulos

AMBITOS = ("docente", "investigador", "estudiante")


def pendiente(tipo: str, titulo: str, detalle: str = "", cuando: str | None = None, href: str | None = None) -> dict:
    return {"tipo": tipo, "titulo": titulo, "detalle": detalle, "cuando": (cuando or None) and cuando[:10], "href": href}


def evento(iso: str | None, titulo: str, tipo: str, detalle: str = "", href: str | None = None) -> dict | None:
    """None si no hay fecha (los aportes lo devuelven tal cual y aquí se descarta)."""
    if not iso:
        return None
    return {"fecha": iso[:10], "hora": iso[11:16] if len(iso) >= 16 else "", "titulo": titulo, "tipo": tipo,
            "detalle": detalle, "href": href}


def situacion(p: dict, hoy: date | None = None) -> str:
    """'vencido', 'proximo' (en los próximos 7 días) o 'normal'."""
    if not p["cuando"]:
        return "normal"
    d = date.fromisoformat(p["cuando"]) - (hoy or date.today())
    return "vencido" if d.days < 0 else "proximo" if d.days <= 7 else "normal"


def pendientes_de(ambito: str, quien: int, hoy: date | None = None) -> list[dict]:
    """Lo que la persona debe hacer según los módulos activos: lo que vence antes primero y lo sin fecha, después."""
    hoy = hoy or date.today()
    todos = [p for aporte in modulos.aportes("pendientes") for p in aporte(ambito, quien, hoy)]
    return sorted(todos, key=lambda p: (p["cuando"] is None, p["cuando"] or "", p["titulo"]))


def eventos_de(ambito: str, quien: int, desde: date | None = None, hasta: date | None = None) -> list[dict]:
    """Las fechas de la persona entre `desde` y `hasta` (por omisión, de hoy a 120 días), en orden."""
    desde = desde or date.today()
    hasta = hasta or desde + timedelta(days=120)
    d, h = desde.isoformat(), hasta.isoformat()
    todos = [e for aporte in modulos.aportes("eventos") for e in aporte(ambito, quien, desde, hasta) if e]
    return sorted((e for e in todos if d <= e["fecha"] <= h), key=lambda e: (e["fecha"], e["hora"], e["titulo"]))


def bloques(auth: dict, volver: str) -> list:
    """Bloques que los módulos activos ponen sobre la lista de pendientes (p. ej., «Mi parte del plan de mejora»)."""
    return [b for aporte in modulos.aportes("bloque_pendientes") if (b := aporte(auth, volver))]


def _ics(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace(";", r"\;").replace(",", "\\,").replace("\n", "\\n")


def ics(lista: list[dict], nombre: str = "TAU", titulo: str = "Calendario del estudiante") -> str:
    """Los eventos como archivo de calendario (.ics) para Google Calendar, Outlook o el teléfono."""
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{nombre}//{titulo}//ES", "CALSCALE:GREGORIAN"]
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
