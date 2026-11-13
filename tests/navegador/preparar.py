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

from app.academico import cambios, gestiones, menciones, oferta, reformas, semestre
from app.estudiantil import tutoria
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
ESTUDIANTES = ("Sofía", "Rosa", "Julia", "Marta", "Elena", "Paula")


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


def _servicios_del_estudiante(emmy, direccion_id):
    """Datos para las pantallas de los servicios del estudiante (PLAN §67): plan, tutor, oportunidad, tema, recurso, orientación
    y un evento con inscripción."""
    from app.estudiantil import orientacion
    from app.servicios import comunicados as com
    from app.servicios import oportunidades, recursos, temas
    db = get_db()
    plan = db.q("""SELECT p.id FROM plan_estudios p JOIN programa pr ON pr.id = p.programa_id
                   WHERE pr.nombre = 'Licenciatura en Matemática' AND p.estado = 'vigente'""")[0]["id"]
    db.execute("UPDATE estudiante SET plan_id = ?", [plan])
    cuentas = db.q("SELECT externo_id, usuario_id FROM cuenta_estudiante")
    for c in cuentas:
        assert tutoria.asignar(c["externo_id"], emmy, None) == []
    direccion = usuarios.por_id(direccion_id)
    doc = usuarios.por_id(emmy)
    oid, errores = oportunidades.crear({"tipo": "beca", "titulo": "Beca de excelencia académica", "para": "estudiantes",
                                        "descripcion": "Para estudiantes con buen desempeño.", "cierre": (date.today() + timedelta(days=30)).isoformat()},
                                       direccion)
    assert not errores, errores
    assert oportunidades.cambiar_estado(oid, "publicada", direccion) == []
    tid, errores = temas.crear({"titulo": "Coloraciones de grafos", "descripcion": "Un tema de combinatoria", "cupos": "2"}, doc)
    assert not errores, errores
    assert temas.cambiar_estado(tid, "publicado", doc) == []
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    _, errores = recursos.crear({"tipo": "guia", "titulo": "Guía de ejercicios de Álgebra I"},
                                [str(db.q("SELECT id FROM asignatura WHERE sigla = 'MAT-111'")[0]["id"])], doc, (pdf, "guia.pdf"))
    assert not errores, errores
    assert orientacion.guardar_pregunta({"categoria": "Trámites", "pregunta": "¿Dónde pido una constancia?",
                                         "respuesta": "En Kardex, con su RU."}, direccion_id) == []
    assert orientacion.guardar_servicio({"tipo": "bienestar", "nombre": "Bienestar universitario", "contacto": "Edificio central"},
                                        direccion_id) == []
    inicio = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%dT15:00")
    x, errores = com.validar({"tipo": "evento", "titulo": "Curso corto de LaTeX", "publica_como": "direccion_carrera", "inicio": inicio,
                              "lugar": "Laboratorio", "inscripcion": "1", "cupos": "20", "horas": "8", "certificado": "1"},
                             [("direccion_carrera", "Dirección de Carrera")])
    assert not errores, errores
    cid = com.crear(x, direccion_id)
    com.agregar_convocados(cid, [c["usuario_id"] for c in cuentas])
    assert com.publicar(cid) == []


def _gestion_activa(emmy, grace, uid):
    """Un semestre de un año futuro con las fechas puestas para que cubra hoy, con dos paralelos y un docente reasignado."""
    anio = date.today().year + 5
    g, _ = gestiones.crear(anio, "I", uid)
    get_db().execute("UPDATE gestion_academica SET fecha_inicio = ?, fecha_fin = ? WHERE id = ?",
                     [(date.today() - timedelta(days=60)).isoformat(), (date.today() + timedelta(days=60)).isoformat(),
                      g["id"]])
    o1, _ = oferta.agregar(g["id"], "MAT-113", "A", "30", uid)
    o2, _ = oferta.agregar(g["id"], "MAT-114", "A", "28", uid)
    oferta.asignar(o1, emmy, "titular")
    oferta.asignar(o2, grace, "titular")
    assert semestre.activar(g["id"], uid) == []
    did = oferta.docentes(o1)[0]["id"]
    assert cambios.reasignar_docente(did, grace, {"fecha": (date.today() - timedelta(days=10)).isoformat(),
                                                   "motivo": "licencia", "detalle": "Licencia por salud"}, uid) == []
    return gestiones.obtener(g["id"])


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
    # Gestiones (PLAN §66): una activa (id 5, con un cambio ya registrado) y una concluida (id 6) para revisar sus pantallas.
    activa = _gestion_activa(emmy, grace, direccion["id"])
    hist, _ = gestiones.crear(date.today().year - 4, "II", direccion["id"], concluida=True)
    assert (activa["id"], hist["id"]) == (5, 6)
    oferta.agregar(hist["id"], "MAT-111", "A", "35", emmy)
    _servicios_del_estudiante(emmy, direccion["id"])
    # Planes (PLAN §65): una reforma en elaboración (reforma 2; plan 5 = Licenciatura en Matemática copiada, plan 6 = Maestría
    # en Matemática vacía) con una mención, para revisar las pantallas del módulo.
    ids = {r["nombre"]: r["id"] for r in get_db().q("SELECT id, nombre FROM programa")}
    reformas.crear(direccion["id"], "Plan 2027", "HCU 9/2027", "2027",
                   {ids["Licenciatura en Matemática"]: "copia", ids["Maestría en Matemática"]: "vacio"}, [])
    plan = get_db().q("SELECT id FROM plan_estudios WHERE nombre = 'Plan 2027' AND programa_id = ?",
                      [ids["Licenciatura en Matemática"]])[0]["id"]
    menciones.guardar(plan, None, {"nombre": "Matemática Pura", "semestre_eleccion": "6"}, direccion["id"])
    hoy = date.today()
    periodo = institucionales.periodo_objetivo()
    institucionales.guardar_plazo(periodo, hoy.isoformat(), (hoy + timedelta(days=30)).isoformat(), 1)


if __name__ == "__main__":
    preparar(sys.argv[1])
