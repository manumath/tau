"""Módulos que declara `app/servicios` (PLAN §73)."""
from app.comun.modulos import Modulo
from app.servicios import aportes

_R = "app.servicios.rutas."

MODULOS = (
    Modulo(
        "comunicados", "Comunicados y eventos",
        "Comunicados a la comunidad y eventos con convocados e inscripción.",
        area="Servicios", rutas=(_R + "comunicados",), acciones=("publicar_comunicados",),
        aportes={"menu": aportes.menu_comunicados, "menu_estudiante": aportes.portal_comunicados,
                 "pendientes": aportes.pendientes_comunicados, "eventos": aportes.eventos_comunicados}),
    Modulo(
        "auxiliaturas", "Auxiliaturas",
        "Convocatorias a auxiliares académicos: comisión, calificación por formularios, designaciones e impresos.",
        area="Servicios", requiere=("oferta", "estudiantes"),
        rutas=tuple(_R + m for m in ("auxiliaturas", "designaciones", "formularios")),
        acciones=("gestionar_auxiliaturas", "gestionar_auxiliaturas_investigacion"),
        aportes={"menu": aportes.menu_auxiliaturas, "menu_estudiante": aportes.portal_auxiliaturas,
                 "pendientes": aportes.pendientes_auxiliaturas, "eventos": aportes.eventos_auxiliaturas,
                 "en_curso": aportes.en_curso_auxiliaturas, "historial": aportes.historial_auxiliaturas,
                 "certificados": aportes.certificados_auxiliaturas,
                 "titulares_de_certificados": aportes.titulares_auxiliaturas},
        privacidad=("auxiliaturas",)),
    Modulo(
        "grado", "Proyectos de grado",
        "Trámites de titulación (perfil y documento final, tutor, tribunal y revisiones) y temas de grado.",
        area="Servicios", requiere=("estudiantes",), rutas=(_R + "grado", _R + "temas"),
        acciones=("gestionar_grado",),
        aportes={"menu": aportes.menu_grado, "menu_estudiante": aportes.portal_grado,
                 "pendientes": aportes.pendientes_grado, "eventos": aportes.eventos_grado,
                 "mantenimiento": aportes.MANTENIMIENTO_GRADO, "en_curso": aportes.en_curso_grado,
                 "historial": aportes.historial_grado, "certificados": aportes.certificados_grado,
                 "titulares_de_certificados": aportes.titulares_grado}),
    Modulo(
        "oportunidades", "Oportunidades y biblioteca",
        "Becas, movilidad, pasantías y empleo para estudiantes, y la biblioteca de recursos.",
        area="Servicios", requiere=("estudiantes",), rutas=(_R + "oportunidades", _R + "recursos"),
        acciones=("gestionar_oportunidades", "gestionar_recursos"),
        aportes={"menu": aportes.menu_oportunidades, "menu_estudiante": aportes.portal_oportunidades,
                 "eventos": aportes.eventos_oportunidades, "en_curso": aportes.en_curso_oportunidades},
        privacidad=("oportunidades",)),
)
