"""Base de datos de las pruebas en navegador. Uso: python -m tests.navegador.preparar <ruta.db>

Crea una administradora y una investigadora titular (con vínculo desde 2015) con contraseñas de
prueba definitivas, una integrante de la Comisión de calidad, una persona con las dos direcciones, dos paralelos en
la gestión en curso (uno sin docente), un investigador con más productos de los que caben en una página (para «Cargar
más») y deja abierta la convocatoria institucional durante 30 días desde hoy, para
que el flujo de propuestas no dependa de la fecha en que se ejecuten las pruebas.
"""
import sys
from datetime import date, timedelta

from app.academico import gestiones, oferta
from app.comun import permisos, unidades, usuarios
from app.comun.componentes.registros import POR_PAGINA
from app.comun.db import get_db, init_db
from app.investigacion import institucionales, productos

CLAVE = "Prueba-navegador-1"
ADMIN = "admin@prueba.test"
INVESTIGADORA = "emmy@prueba.test"
PROLIFICO = "alan@prueba.test"
COMISION = "comision@prueba.test"
DIRECCION = "direccion@prueba.test"   # las dos direcciones: ve casi todas las pantallas


def preparar(ruta: str):
    init_db(ruta)
    usuarios.crear(ADMIN, "Ada", "Administradora", CLAVE, es_admin=True, es_investigador=False,
                   debe_cambiar_pass=False)
    emmy = usuarios.crear(INVESTIGADORA, "Emmy", "Noether", CLAVE, debe_cambiar_pass=False, categoria="titular",
                          fecha_ingreso="2015-03-01")["id"]
    comision = usuarios.crear(COMISION, "Mary", "Somerville", CLAVE, debe_cambiar_pass=False, es_investigador=False)
    permisos.asignar(comision["id"], "comision_calidad", unidades.id_de("UMSA"))
    direccion = usuarios.crear(DIRECCION, "Sofía", "Kovalévskaya", CLAVE, debe_cambiar_pass=False, es_investigador=False)
    permisos.asignar(direccion["id"], "direccion_carrera", unidades.id_de("CMAT"))
    permisos.asignar(direccion["id"], "direccion_instituto", unidades.id_de("IIMAT"))
    # Oferta de la gestión en curso: un paralelo con docente y otro sin él (filtro «sin docente»).
    gestiones.crear_anio(date.today().year)
    if (g := gestiones.actual()):
        oid, _ = oferta.agregar(g["id"], "MAT-111", "A", "40", emmy)
        oferta.asignar(oid, emmy, "titular")
        oferta.agregar(g["id"], "MAT-112", "A", "", emmy)
    alan = usuarios.crear(PROLIFICO, "Alan", "Turing", CLAVE, debe_cambiar_pass=False)["id"]
    preprint = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Preprint'")[0]["id"]
    for i in range(POR_PAGINA + 5):
        d, errores = productos.preparar(dict(tipo_id=str(preprint), titulo=f"Nota {i:02d}", anio="2026",
                                             estado_publicacion="publicado", revision="sin_arbitraje"),
                                        [f"i:{alan}"], [])
        assert not errores, errores
        productos.guardar(d, [f"i:{alan}"], alan)
    hoy = date.today()
    periodo = institucionales.periodo_objetivo()
    institucionales.guardar_plazo(periodo, hoy.isoformat(), (hoy + timedelta(days=30)).isoformat(), 1)


if __name__ == "__main__":
    preparar(sys.argv[1])
