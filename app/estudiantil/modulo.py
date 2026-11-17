"""Módulos que declara `app/estudiantil` (PLAN §73)."""
from app.comun.modulos import Modulo
from app.estudiantil import aportes

_R = "app.estudiantil.rutas."

MODULOS = (
    Modulo(
        "estudiantes", "Seguimiento estudiantil",
        "Cohortes desde el CSV de Seguimiento Académico, rendimiento, actividad estudiantil y el portal del estudiante.",
        area="Estudiantes",
        # El informe de seguimiento estudiantil vive en `calidad`, pero es de este módulo.
        rutas=(*(_R + m for m in ("cohortes", "rendimiento", "actividades", "estudiante", "mi_plan", "calendario")),
               "app.calidad.rutas.seguimiento_estudiantil"),
        tambien={_R + "mi_plan": ("planes",)},   # «Mi plan de estudios» necesita los planes
        acciones=("gestionar_cohortes", "verificar_actividad", "ver_seguimiento_estudiantil"),
        aportes={"menu": aportes.menu_estudiantes, "menu_estudiante": aportes.portal_estudiantes,
                 "inicio": aportes.inicio_estudiantes},
        privacidad=("estudiantes",)),
    Modulo(
        "encuestas", "Encuestas",
        "Encuestas a estudiantes y egresados, anónimas o nominales, con su retorno de resultados.",
        area="Estudiantes", requiere=("estudiantes",),
        rutas=tuple(_R + m for m in ("encuestas", "mis_encuestas", "responder")),
        acciones=("gestionar_encuestas",),
        aportes={"menu": aportes.menu_encuestas, "menu_estudiante": aportes.portal_encuestas,
                 "eventos": aportes.eventos_encuestas, "en_curso": aportes.en_curso_encuestas},
        privacidad=("encuestas",)),
    Modulo(
        "tutoria_apoyo", "Tutoría y apoyo",
        "Tutoría confidencial, casos de apoyo estudiantil, orientación y buzón de consultas.",
        area="Estudiantes", requiere=("estudiantes",),
        rutas=tuple(_R + m for m in ("tutoria", "mi_tutoria", "apoyo", "mi_apoyo", "orientacion")),
        acciones=("gestionar_tutorias", "ver_tutorias_detalle", "gestionar_apoyo", "gestionar_buzon"),
        aportes={"menu": aportes.menu_tutoria, "menu_estudiante": aportes.portal_tutoria,
                 "inicio": aportes.inicio_tutoria, "pendientes": aportes.pendientes_tutoria,
                 "eventos": aportes.eventos_tutoria, "en_curso": aportes.en_curso_tutoria,
                 "historial": aportes.historial_tutoria},
        privacidad=("buzon", "apoyo")),
)
