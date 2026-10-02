"""Usuarios: cuentas, carga de cuentas por CSV, roles, ficha académica, vínculo con la Carrera e
historial de vínculos desde Recursos Humanos.

Módulos: comun (fila de la tabla y permisos compartidos), cuentas, importar_cuentas, roles, ficha,
vinculo e historial. Se registran en ese orden."""
from app.comun.rutas.admin_usuarios import cuentas, importar_cuentas, roles, ficha, vinculo, historial


class _Rutas:
    """Registra los routers del paquete en orden (main.py lo usa como un APIRouter)."""

    def to_app(self, app):
        for modulo in (cuentas, importar_cuentas, roles, ficha, vinculo, historial):
            modulo.rt.to_app(app)


rt = _Rutas()
