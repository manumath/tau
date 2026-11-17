"""Fechas y números como se escriben en español de Bolivia (PLAN §62, etapa 3).

Una sola forma en todo el sistema: «8 nov 2026», «8 nov 2026, 22:43», «1 ago – 31 dic 2026» y «2,7». Antes convivían
«2026-08-01», «08-11-2026 22:43» (¿8 de noviembre u 11 de agosto?) y «2.7». Las exportaciones (CSV, XLSX) siguen con
fechas ISO, que las hojas de cálculo entienden.
"""
import re
from datetime import date, datetime, timezone

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _a_fecha(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def fecha(valor, *, anio: bool = True) -> str:
    """'2026-11-08' → '8 nov 2026'. Vacío o ilegible → '—' (o el texto tal cual, si no es una fecha)."""
    d = _a_fecha(valor)
    if d is None:
        return str(valor) if valor else "—"
    return f"{d.day} {MESES[d.month - 1]}" + (f" {d.year}" if anio else "")


def fecha_hora(iso_utc) -> str:
    """Marca de tiempo de SQLite en UTC ('2026-11-09 02:43:11') → hora local: '8 nov 2026, 22:43'."""
    if not iso_utc:
        return "—"
    dt = datetime.fromisoformat(str(iso_utc)).replace(tzinfo=timezone.utc).astimezone()
    return f"{fecha(dt.date())}, {dt:%H:%M}"


def momento(iso_local) -> str:
    """Fecha y hora ya locales, como se escriben en un formulario ('2026-11-12T14:30', cierres de convocatorias,
    eventos) → '12 nov 2026, 14:30'; si es solo fecha, '12 nov 2026'. A diferencia de fecha_hora, no convierte de UTC."""
    if not iso_local:
        return "—"
    texto = str(iso_local)
    hora = texto[11:16] if len(texto) >= 16 and texto[10] in "T " else ""
    return fecha(texto) + (f", {hora}" if hora else "")


_ISO_EN_TEXTO = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b")


def fechas_en_texto(texto) -> str:
    """Las fechas ISO dentro de un texto libre (el detalle de la auditoría: «Hoja 2026-11-03 a 2026-12-01») →
    «Hoja 3 nov 2026 a 1 dic 2026». Lo que no es una fecha válida queda tal cual."""
    def _uno(m):
        d = _a_fecha(m.group())
        return momento(m.group()) if d else m.group()
    return _ISO_EN_TEXTO.sub(_uno, str(texto or ""))


def periodo(desde, hasta) -> str:
    """'1 ago – 31 dic 2026' (mismo año) o '1 ago 2026 – 15 ene 2027'. Sin término: 'desde 1 ago 2026'."""
    a, b = _a_fecha(desde), _a_fecha(hasta)
    if a is None:
        return fecha(hasta)
    if b is None:
        return f"desde {fecha(a)}"
    return f"{fecha(a, anio=a.year != b.year)} – {fecha(b)}"


def numero(valor, decimales: int = 1) -> str:
    """2.7 → '2,7'; 36.0 → '36'; miles con punto: 1500 → '1.500'. None → '—'."""
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}" if isinstance(valor, float) else f"{valor:,}"
    if "." in texto and isinstance(valor, float):
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")
