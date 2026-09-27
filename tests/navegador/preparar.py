"""Base de datos de las pruebas en navegador. Uso: python -m tests.navegador.preparar <ruta.db>

Crea una administradora y una investigadora titular (con vínculo desde 2015) con contraseñas de
prueba definitivas, y deja abierta la convocatoria institucional durante 30 días desde hoy, para
que el flujo de propuestas no dependa de la fecha en que se ejecuten las pruebas.
"""
import sys
from datetime import date, timedelta

from app.comun import usuarios
from app.comun.db import init_db
from app.investigacion import institucionales

CLAVE = "Prueba-navegador-1"
ADMIN = "admin@prueba.test"
INVESTIGADORA = "emmy@prueba.test"


def preparar(ruta: str):
    init_db(ruta)
    usuarios.crear(ADMIN, "Ada", "Administradora", CLAVE, es_admin=True, es_investigador=False,
                   debe_cambiar_pass=False)
    usuarios.crear(INVESTIGADORA, "Emmy", "Noether", CLAVE, debe_cambiar_pass=False, categoria="titular",
                   fecha_ingreso="2015-03-01")
    hoy = date.today()
    periodo = institucionales.periodo_objetivo()
    institucionales.guardar_plazo(periodo, hoy.isoformat(), (hoy + timedelta(days=30)).isoformat(), 1)


if __name__ == "__main__":
    preparar(sys.argv[1])
