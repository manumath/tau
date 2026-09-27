"""«Mis productos»: lista con filtros, alta/edición en modal, ficha con adjuntos.

Patrones HTMX:
- La lista escucha el evento `productos-cambiados`; tras guardar o eliminar, el servidor lo
  dispara con la cabecera HX-Trigger y la lista se recarga con los filtros vigentes.
- El bloque «revisión / índices / actividad» depende del tipo y del nivel de revisión elegidos:
  se vuelve a pedir al servidor cuando cambian (/productos/campos).
- Al escribir un DOI o arXiv se avisa si el producto ya existe (/productos/verificar).

Módulos: lista, formulario, carga_openalex y ficha. Se registran en ese orden: la ficha va al final
porque «/productos/{pid}» capturaría las rutas literales («/productos/nuevo», «/productos/campos»,
«/productos/openalex», «/productos/revistas»)."""
from app.investigacion.rutas.productos import lista, formulario, carga_openalex, ficha


class _Rutas:
    """Registra los routers del paquete en orden (main.py lo usa como un APIRouter)."""

    def to_app(self, app):
        for modulo in (lista, formulario, carga_openalex, ficha):
            if hasattr(modulo, "rt"):
                modulo.rt.to_app(app)


rt = _Rutas()
