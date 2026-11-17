"""Módulos que declara `app/investigacion` (PLAN §73)."""
from app.comun.modulos import Modulo
from app.investigacion import aportes, mis_pendientes

MODULOS = (
    Modulo(
        "investigacion", "Investigación",
        "Perfiles de investigadores, productos, actividades, proyectos y propuestas, con el directorio público y la API.",
        area="Investigación", rutas=("app.investigacion.rutas",),
        acciones=("decidir_propuestas", "gestionar_convocatoria", "gestionar_catalogos", "reasignar_responsable",
                  "actualizar_citas", "ver_todos_los_proyectos", "ver_propuestas", "ver_evidencias"),
        aportes={"menu": aportes.menu, "busqueda": aportes.BUSQUEDA, "inicio": aportes.inicio, "cifras": aportes.cifras,
                 "pendientes": mis_pendientes.aporte_pendientes, "eventos": mis_pendientes.aporte_eventos,
                 "mantenimiento": aportes.MANTENIMIENTO, "en_curso": aportes.en_curso, "historial": aportes.historial},
        privacidad=("perfil",)),
)
