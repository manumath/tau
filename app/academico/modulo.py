"""Módulos que declara `app/academico` (PLAN §73)."""
from app.academico import aportes, docente
from app.comun.modulos import Modulo

_R = "app.academico.rutas."

MODULOS = (
    Modulo(
        "planes", "Planes de estudio",
        "Reformas curriculares, planes, malla, menciones y equivalencias entre planes.",
        area="Docencia", rutas=tuple(_R + m for m in ("planes", "malla", "equivalencias", "vigencia")),
        acciones=("revisar_planes", "elaborar_planes", "decidir_planes"),
        aportes={"menu": aportes.menu_planes, "busqueda": aportes.BUSQUEDA_PLANES}),
    Modulo(
        "oferta", "Oferta y asignación docente",
        "Gestiones, oferta de materias, asignación de docentes, carga horaria asignada y los servicios del docente.",
        area="Docencia", requiere=("planes",),
        # El informe del cuerpo académico y de carga docente vive en `calidad`, pero es de docencia.
        rutas=(*(_R + m for m in ("oferta", "carga", "mi_docencia", "mis_pendientes", "preferencias", "programas", "listas",
                                  "historial", "renovaciones", "preparacion")),
               "app.calidad.rutas.cuerpo_academico"),
        acciones=("gestionar_oferta", "decidir_gestion", "ver_carga"),
        aportes={"menu": aportes.menu_oferta, "inicio": aportes.inicio_oferta, "pendientes": docente.aporte_pendientes,
                 "eventos": docente.aporte_eventos, "en_curso": aportes.en_curso_oferta}),
    Modulo(
        "evaluacion_docente", "Evaluación docente",
        "Evaluación anónima de los docentes por sus estudiantes, con resultados por paralelo.",
        area="Docencia", requiere=("oferta", "estudiantes"),
        rutas=(_R + "evaluacion", "app.estudiantil.rutas.evaluacion"),
        acciones=("gestionar_evaluacion_docente",),
        aportes={"menu": aportes.menu_evaluacion, "menu_estudiante": aportes.portal_evaluacion,
                 "en_curso": aportes.en_curso_evaluacion},
        privacidad=("evaluacion_docente",)),
)
