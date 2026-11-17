"""Proyectos: lista, alta de proyectos individuales, ficha con pestañas, bandeja de pendientes y
reasignación del responsable (administración).

Patrones HTMX:
- Pestañas: cada una se pide a /proyectos/{id}/tab/{nombre}; el servidor fija ?tab= en la URL
  (HX-Replace-Url), así una pestaña se puede recargar o compartir.
- Tras aprobar o rechazar, la respuesta trae la bandeja actualizada, el contador de la pestaña
  fuera de banda y el evento `pendientes-cambiados` para el contador de la navegación.

Módulos: lista, datos, resumen, participantes, registros, pendientes, plan, reasignar y ficha. Se
registran en ese orden: la ficha va al final porque «/proyectos/{pid}» capturaría las rutas literales
(«/proyectos/nuevo», «/proyectos/pendientes/contador»)."""
from app.investigacion.rutas.proyectos import (lista, datos, resumen, participantes, registros, pendientes, plan,
                                               reasignar, ficha)


class _Rutas:
    """Registra los routers del paquete en orden (main.py lo usa como un APIRouter)."""

    def to_app(self, app):
        for modulo in (lista, datos, resumen, participantes, registros, pendientes, plan, reasignar, ficha):
            if hasattr(modulo, "rt"):
                modulo.rt.to_app(app)


rt = _Rutas()
