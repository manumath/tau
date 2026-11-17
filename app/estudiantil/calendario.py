"""Calendario académico del estudiante (PLAN §67, etapa 2): sus fechas en un solo lugar. No guarda nada: junta lo que
aporta cada módulo activo (semestres, convocatorias, defensas, eventos, becas, reuniones de tutoría, encuestas; PLAN §73,
etapa 3). Cada evento: {fecha, hora, titulo, tipo, detalle, href} (`app/comun/calendario.py`)."""
from datetime import date

from app.comun import calendario
from app.comun.calendario import ics  # noqa: F401  (lo usan las rutas del calendario)

TIPOS = {"gestion": "Semestre", "evento": "Evento", "auxiliatura": "Auxiliaturas", "grado": "Grado", "oportunidad": "Oportunidad",
         "tutoria": "Tutoría", "encuesta": "Encuesta"}


def eventos(externo_id: int, desde: date | None = None, hasta: date | None = None) -> list[dict]:
    """Las fechas del estudiante entre `desde` y `hasta` (por omisión, de hoy a 120 días), en orden."""
    return calendario.eventos_de("estudiante", externo_id, desde, hasta)
