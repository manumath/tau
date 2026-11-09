"""Base de datos de las pruebas en navegador. Uso: python -m tests.navegador.preparar <ruta.db>

Crea una administradora y una investigadora titular (con vínculo desde 2015) con contraseñas de
prueba definitivas, una integrante de la Comisión de calidad, una persona con las dos direcciones, dos paralelos en
la gestión en curso (uno sin docente), una estudiante con enlaces de ingreso, una convocatoria a auxiliaturas
abierta, un investigador con más productos de los que caben en una página (para «Cargar
más») y deja abierta la convocatoria institucional durante 30 días desde hoy, para
que el flujo de propuestas no dependa de la fecha en que se ejecuten las pruebas.
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from app.academico import gestiones, oferta
from app.comun import estudiantes, permisos, tokens, unidades, usuarios
from app.comun.componentes.registros import POR_PAGINA
from app.comun.db import get_db, init_db
from app.investigacion import institucionales, productos
from app.servicios import auxiliaturas as aux

CLAVE = "Prueba-navegador-1"
ADMIN = "admin@prueba.test"
INVESTIGADORA = "emmy@prueba.test"
PROLIFICO = "alan@prueba.test"
COMISION = "comision@prueba.test"
DIRECCION = "direccion@prueba.test"   # las dos direcciones: ve casi todas las pantallas
# Estudiantes con cuenta, sin haber aceptado el consentimiento: una por prueba que entra como estudiante, porque cada
# enlace de ingreso anula el anterior de la misma cuenta.
ESTUDIANTES = ("Sofía", "Rosa", "Julia", "Marta")


def archivo_enlaces(ruta_db: str) -> Path:
    """Donde quedan los enlaces de ingreso de las estudiantes (el correo de las pruebas no sale del servidor)."""
    return Path(ruta_db).with_suffix(".enlaces")


def _estudiante(nombre, email, ru, consentimiento=True):
    p = get_db().t.persona_externa.insert(nombres=nombre, apellidos="Estudiante", email=email)
    get_db().t.estudiante.insert(externo_id=p["id"], nivel="licenciatura", desde=2022, registro_universitario=ru,
                                 cohorte_anio=2022, cohorte_ciclo="I")
    u = estudiantes.crear_cuenta(p["id"], None)
    if consentimiento:
        estudiantes.aceptar_consentimiento(p["id"])
    return u["id"]


def _convocatoria(gestion, asignatura_id, docentes, tribunal_estudiantes):
    """Convocatoria a auxiliaturas publicada, con la recepción abierta 3 días."""
    ahora = datetime.now()
    x, errores = aux.validar({"modalidad": "docencia", "gestion_id": gestion["id"], "numero": "1",
                              "titulo": "Auxiliaturas de prueba", "publicacion": date.today().isoformat(),
                              "cierre": (ahora + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
                              "examen": (ahora + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M"),
                              "resolucion": "Res. CC 1/2026"}, ["docencia"])
    assert not errores, errores
    cid = aux.crear(x, docentes[0])
    assert aux.agregar_item(aux.obtener(cid), {"asignatura_id": asignatura_id, "plazas": "1", "horas": "40"}) == []
    assert aux.fijar_tribunal(aux.items(cid)[0], docentes, tribunal_estudiantes) == []
    assert aux.publicar(cid) == [], aux.publicar(cid)


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
    g = gestiones.actual()
    oid, _ = oferta.agregar(g["id"], "MAT-111", "A", "40", emmy)
    oferta.asignar(oid, emmy, "titular")
    oferta.agregar(g["id"], "MAT-112", "A", "", emmy)
    # Servicios (PLAN §58): una estudiante que postula y presenta su perfil, y una convocatoria abierta con tribunal.
    grace = usuarios.crear("grace@prueba.test", "Grace", "Hopper", CLAVE, debe_cambiar_pass=False, categoria="titular",
                           fecha_ingreso="2018-02-01")["id"]
    cuentas = [_estudiante(n, f"estudiante{i}@prueba.test", f"91{i}", consentimiento=False)
               for i, n in enumerate(ESTUDIANTES)]
    tribunal = [_estudiante("Luis", "luis@prueba.test", "902"), _estudiante("Ana", "ana@prueba.test", "903")]
    asignatura = get_db().q("SELECT asignatura_id FROM oferta WHERE id = ?", [oid])[0]["asignatura_id"]
    _convocatoria(g, asignatura, [emmy, grace], tribunal)
    archivo_enlaces(ruta).write_text("\n".join(f"/acceso/{tokens.emitir(u, 'acceso')}" for u in cuentas))
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
