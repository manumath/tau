"""Carga datos de demostración.

    uv run python scripts/seed.py            # agrega lo que falte
    uv run python scripts/seed.py --reset    # borra la BD y la recrea

Las contraseñas de demostración son fijas para poder probar el portal; en
producción las cuentas se crean desde Administración → Usuarios.
"""
import shutil
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json  # noqa: E402

from app.academico import gestiones, oferta  # noqa: E402
from app.investigacion import (actividades, carga_proyectos, institucionales, lineas, msc, perfiles,  # noqa: E402
                               productos, proyectos, revistas)
from app.comun import academicos, config, estudiantes, personas, usuarios, vinculos  # noqa: E402
from app.comun.db import AHORA, get_db, marca_tiempo  # noqa: E402
from app.comun.db import init_db  # noqa: E402

ADMIN = dict(email="admin@instituto.test", nombres="Ada", apellidos="Administradora",
             password="Admin-portal-2026", es_admin=True, es_investigador=False,
             debe_cambiar_pass=False)
INVESTIGADORES = [
    # Contraseña temporal común: el portal obliga a cambiarla en el primer ingreso.
    dict(email="sofia.kovalevskaya@instituto.test", nombres="Sofía", apellidos="Kovalévskaya",
         es_admin=True, categoria="titular"),
    dict(email="emmy.noether@instituto.test", nombres="Emmy", apellidos="Noether", categoria="titular"),
    dict(email="alan.turing@instituto.test", nombres="Alan", apellidos="Turing", categoria="contratado"),
    dict(email="srinivasa.ramanujan@instituto.test", nombres="Srinivasa", apellidos="Ramanujan",
         categoria="invitado"),
]
PASS_TEMPORAL_DEMO = "Temporal-2026"

# Perfiles de ejemplo (el de Ramanujan queda vacío para ver un perfil por completar).
# El ORCID es el de Josiah Carberry, investigador ficticio que ORCID usa para pruebas.
PERFILES = {
    "sofia.kovalevskaya@instituto.test": dict(
        grados=[dict(nivel="doctorado", titulo="Doctora en Matemáticas", institucion="Universidad de Gotinga",
                     pais="Alemania", anio=1998)],
        areas=["35-XX", "70E17", "35Q35"],
        bio="Estudio el movimiento de un cuerpo rígido alrededor de un punto fijo y la existencia "
            "de soluciones analíticas de ecuaciones en derivadas parciales."),
    "emmy.noether@instituto.test": dict(
        grados=[dict(nivel="doctorado", titulo="Doctora en Matemáticas", institucion="Universidad de Erlangen",
                     pais="Alemania", anio=2005)],
        zbmath_id="noether.emmy", areas=["13-XX", "13E05", "16-XX", "17-XX"],
        bio="Trabajo en álgebra conmutativa y no conmutativa: anillos que satisfacen la condición "
            "de cadena ascendente, $I_1 \\subseteq I_2 \\subseteq \\cdots$, y teoría de ideales.\n\n"
            "También me interesan las relaciones entre simetrías y leyes de conservación:\n"
            "$$\\frac{d}{dt}\\left(\\frac{\\partial L}{\\partial \\dot q}\\,\\delta q\\right) = 0.$$"),
    "alan.turing@instituto.test": dict(
        grados=[dict(nivel="doctorado", titulo="PhD in Mathematics", institucion="Princeton University",
                     pais="Estados Unidos", anio=2010),
                dict(nivel="licenciatura", titulo="Bachelor of Arts in Mathematics",
                     institucion="King's College, Cambridge", pais="Reino Unido", anio=2006)],
        orcid="0000-0002-1825-0097", arxiv_id="turing_a_1", areas=["03D10", "68Q04", "03-XX"],
        bio=None),
}


def _id_tipo(tabla: str, nombre: str) -> int:
    return get_db().q(f"SELECT id FROM {tabla} WHERE nombre = ?", [nombre])[0]["id"]


def _cargar_produccion():
    """Actividades y productos de ejemplo (solo si aún no hay ninguno). True si los cargó."""
    if get_db().q("SELECT 1 FROM producto UNION ALL SELECT 1 FROM actividad LIMIT 1"):
        return False
    uid = {e.split(".")[0]: usuarios.por_email(e)["id"]
           for e in ("emmy.noether@instituto.test", "alan.turing@instituto.test")}
    emmy, turing = f"i:{uid['emmy']}", f"i:{uid['alan']}"
    weyl = f"e:{personas.crear_externo('Hermann', 'Weyl', 'Institute for Advanced Study', 'EE. UU.', uid['emmy'])['id']}"
    alexandrov = f"e:{personas.crear_externo('Pavel', 'Alexandrov', 'Universidad Estatal de Moscú', 'Rusia', uid['emmy'])['id']}"

    def actividad(creador, tipo, participantes, **d):
        base = dict(institucion=None, lugar=None, pais=None, fecha_fin=None, modalidad="presencial",
                    url=None, descripcion=None)
        return actividades.guardar({**base, **d, "tipo_id": _id_tipo("tipo_actividad", tipo)},
                                   participantes, creador)

    congreso = actividad(uid["emmy"], "Congreso", [(emmy, "expositor"), (weyl, "asistente")],
                         titulo="Congreso Internacional de Álgebra Conmutativa",
                         institucion="Universidad de Zúrich", lugar="Zúrich", pais="Suiza",
                         fecha_inicio="2026-07-06", fecha_fin="2026-07-10", ambito="internacional")
    actividad(uid["emmy"], "Seminario", [(emmy, "organizador"), (turing, "asistente")],
              titulo="Seminario de Álgebra del Instituto", lugar="Sala 2", fecha_inicio="2026-04-15",
              ambito="local", modalidad="hibrida")
    actividad(uid["alan"], "Visita de investigación", [(turing, "expositor")],
              titulo="Visita al grupo de Lógica", institucion="Universidad de Princeton",
              lugar="Princeton", pais="EE. UU.", fecha_inicio="2025-10-01", fecha_fin="2025-12-15",
              ambito="internacional")

    def producto(creador, tipo, autores, indices=(), **d):
        base = dict(estado_publicacion="publicado", revision="sin_arbitraje", medio=None,
                    volumen=None, numero=None, paginas=None, doi=None, arxiv_id=None, url=None,
                    resumen=None, actividad_id=None)
        ids = [str(_id_tipo("indice", n)) for n in indices]
        datos, errores = productos.preparar({**base, **d, "tipo_id": str(_id_tipo("tipo_producto", tipo))},
                                            autores, ids)
        assert not errores, errores
        productos.guardar(datos, autores, creador)

    # 10.5555 es el prefijo de pruebas de Crossref: estos DOI no apuntan a nada real.
    producto(uid["emmy"], "Artículo en revista", [emmy, weyl],
             ["Web of Science (SCIE)", "Scopus", "MathSciNet"], revision="indexado",
             titulo="Anillos con condición de cadena ascendente y sus ideales primarios",
             anio="2026", mes="3", medio="Revista de Álgebra", volumen="83", numero="2", paginas="24–66",
             doi="10.5555/demo.2026.001",
             resumen="Probamos que en un anillo noetheriano todo ideal $I$ admite una "
                     "descomposición primaria $I = Q_1 \\cap \\cdots \\cap Q_n$.")
    producto(uid["alan"], "Artículo en revista", [turing, emmy, alexandrov],
             ["Scopus", "zbMATH Open"], revision="indexado", estado_publicacion="aceptado",
             titulo="Invariantes algebraicos de máquinas de estados finitos", anio="2026",
             medio="Journal of Symbolic Logic", arxiv_id="2601.01234")
    producto(uid["alan"], "Artículo en revista", [turing], revision="arbitrado",
             estado_publicacion="enviado", titulo="Morfogénesis y ecuaciones de reacción-difusión",
             anio="2026")
    producto(uid["alan"], "Reporte de investigación", [turing],
             titulo="Sobre números computables: notas del seminario", anio="2025",
             medio="Reportes de investigación del Instituto, n.º 7")
    producto(uid["emmy"], "Presentación", [emmy], titulo="Ideales primarios en anillos noetherianos",
             anio="2026", actividad_id=str(congreso))
    return True


def _cargar_proyectos():
    """Dos proyectos de ejemplo con vínculos aprobados, pendientes y rechazados: uno institucional
    (IIMAT-IDH-2025-01, de Emmy) y uno individual (de Sofía)."""
    if get_db().q("SELECT 1 FROM proyecto LIMIT 1") or not get_db().q("SELECT 1 FROM producto LIMIT 1"):
        return False
    uid = {u["email"].split(".")[0]: u["id"] for u in usuarios.listar()}
    emmy, alan, sofia, srini = uid["emmy"], uid["alan"], uid["sofia"], uid["srinivasa"]
    weyl = get_db().q("SELECT id FROM persona_externa WHERE apellidos = 'Weyl'")[0]["id"]

    def id_de(tabla, titulo):
        return get_db().q(f"SELECT id FROM {tabla} WHERE titulo = ?", [titulo])[0]["id"]

    base = dict(descripcion=None, objetivo_general=None, fuente_financiamiento=None, monto=None,
                fecha_fin=None)
    algebra = proyectos.crear({**base, "codigo": "IIMAT-IDH-2025-01", "estado": "vigente",
                               "nombre": "Estructuras algebraicas y computación",
                               "fecha_inicio": "2025-10-01", "fecha_fin": "2026-09-30",
                               "fuente_financiamiento": "Recursos IDH – UMSA", "monto": 150000,
                               "descripcion": "Estudio de invariantes algebraicos de modelos de cómputo "
                                              "y de anillos noetherianos asociados.",
                               "objetivo_general": "Caracterizar algebraicamente clases de máquinas de "
                                                   "estados mediante sus anillos de invariantes."},
                              emmy, emmy, tipo="institucional")
    for texto in ("Construir el anillo de invariantes de una máquina de estados finitos.",
                  "Determinar cuándo dicho anillo es noetheriano.",
                  "Formar a un estudiante de doctorado en la línea."):
        proyectos.agregar_objetivo(algebra, texto)
    proyectos.agregar_participante(algebra, f"i:{alan}", "co_investigador", True)
    proyectos.agregar_participante(algebra, f"i:{srini}", "tesista", True)
    proyectos.agregar_participante(algebra, f"e:{weyl}", "colaborador", True)

    rigido = proyectos.crear({**base, "codigo": "ISP-BOL-2025", "estado": "vigente",
                              "fuente_financiamiento": "International Science Programme (ISP, Suecia)",
                              "nombre": "Ecuaciones diferenciales y mecánica del sólido rígido",
                              "fecha_inicio": "2025-03-01", "fecha_fin": "2028-02-29"}, sofia, sofia)
    proyectos.agregar_participante(rigido, f"i:{emmy}", "co_investigador", True)

    # En los datos de ejemplo, el equipo participa desde el inicio de cada proyecto.
    get_db().execute("""UPDATE proyecto_participante SET fecha_desde =
                        (SELECT fecha_inicio FROM proyecto WHERE id = proyecto_id)""")

    # Emmy (responsable) vincula lo suyo: queda aprobado de inmediato.
    proyectos.sincronizar("producto", id_de("producto", "Anillos con condición de cadena ascendente y "
                                                         "sus ideales primarios"), [algebra], {"id": emmy})
    seminario = id_de("actividad", "Seminario de Álgebra del Instituto")
    proyectos.sincronizar("actividad", seminario, [algebra], {"id": emmy})
    part_alan = get_db().q("SELECT id FROM proyecto_participante WHERE proyecto_id = ? AND investigador_id = ?",
                           [algebra, alan])[0]["id"]
    proyectos.asignar_responsable_actividad(seminario, algebra, part_alan)
    # Alan (participante) propone: queda pendiente para que Emmy lo revise.
    proyectos.sincronizar("producto", id_de("producto", "Invariantes algebraicos de máquinas de estados "
                                                         "finitos"), [algebra], {"id": alan})
    proyectos.sincronizar("actividad", id_de("actividad", "Visita al grupo de Lógica"), [algebra], {"id": alan})
    reporte = id_de("producto", "Sobre números computables: notas del seminario")
    proyectos.sincronizar("producto", reporte, [algebra], {"id": alan})
    proyectos.rechazar("producto", reporte, algebra, emmy,
                       "Es un trabajo previo de lógica: no corresponde a los objetivos del proyecto.")
    return True


def _cargar_institucionales():
    """Propuestas de ejemplo (solo si aún no hay ninguna). True si las cargó.

    - IIMAT-IDH-2025-01 (Emmy): aceptado para el periodo 2025–2026, que termina el 30 de septiembre
      de 2026: sirve para ver el aviso y la propuesta de continuidad.
    - «Sistemas integrables…» (Sofía): propuesta nueva enviada, para decidir desde la
      administración.
    """
    db = get_db()
    if db.q("SELECT 1 FROM propuesta_institucional LIMIT 1"):
        return False
    algebra = db.q("SELECT * FROM proyecto WHERE codigo = 'IIMAT-IDH-2025-01' AND tipo = 'institucional'")
    if not algebra:
        return False
    algebra = algebra[0]
    emmy = usuarios.por_email("emmy.noether@instituto.test")["id"]
    sofia = usuarios.por_email("sofia.kovalevskaya@instituto.test")["id"]
    admin = usuarios.por_email(ADMIN["email"])["id"]

    def propuesta(pid, periodo, proponente, contenido, objetivos, actividades, estado):
        prop = db.t.propuesta_institucional.insert(proyecto_id=pid, periodo=periodo, modalidad="nuevo",
                                                   proponente_id=proponente, **contenido)["id"]
        for i, texto in enumerate(objetivos):
            db.t.propuesta_objetivo.insert(propuesta_id=prop, orden=i, texto=texto)
        for i, (mes, texto) in enumerate(actividades):
            db.t.propuesta_actividad_prevista.insert(propuesta_id=prop, orden=i, descripcion=texto, mes_previsto=mes)
        copia = json.dumps(institucionales.copia(institucionales.obtener(prop)), ensure_ascii=False)
        db.execute("""UPDATE propuesta_institucional SET estado = 'enviada', envios = 1,
                      enviada_en = ?, copia_enviada = ? WHERE id = ?""",
                   [marca_tiempo(-timedelta(days=3)), copia, prop])
        db.t.propuesta_evento.insert(propuesta_id=prop, accion="enviada", usuario_id=proponente)
        if estado == "aceptada":
            db.execute(f"""UPDATE propuesta_institucional SET estado = 'aceptada', decidida_por = ?,
                          decidida_en = {AHORA} WHERE id = ?""", [admin, prop])
            db.t.propuesta_evento.insert(propuesta_id=prop, accion="aceptada", usuario_id=admin)
        return prop

    propuesta(algebra["id"], 2025, emmy,
              dict(nombre=algebra["nombre"], descripcion=algebra["descripcion"],
                   objetivo_general=algebra["objetivo_general"],
                   metodologia="Asociamos a cada máquina de estados finitos un anillo de invariantes "
                               "$R_M = k[x_1, \\dots, x_n]^{G_M}$ y estudiamos su estructura con técnicas de "
                               "álgebra conmutativa (bases de Gröbner, series de Hilbert).",
                   resultados_esperados="Dos artículos en revistas indexadas y una tesis doctoral en curso.",
                   bibliografia="Noether, E. (1921). Idealtheorie in Ringbereichen. Math. Ann. 83.\n"
                                "Turing, A. M. (1936). On computable numbers. Proc. London Math. Soc."),
              [o["texto"] for o in proyectos.objetivos(algebra["id"])],
              [("2025-10", "Seminario de lanzamiento del proyecto"), ("2026-01", "Escuela de verano de álgebra"),
               ("2026-06", "Visita al grupo de Lógica")], "aceptada")
    institucionales.refrescar_vigencias(algebra["id"])

    periodo = institucionales.periodo_objetivo()
    pid = db.t.proyecto.insert(nombre="Sistemas integrables y geometría de trompos", estado="formulacion",
                               tipo="institucional", clase="investigacion", fecha_inicio=institucionales.inicio(periodo),
                               fecha_fin=institucionales.fin(periodo), creado_por=sofia)["id"]
    db.t.proyecto_participante.insert(proyecto_id=pid, investigador_id=sofia, rol="responsable",
                                      fecha_desde=date.today().isoformat())
    propuesta(pid, periodo, sofia,
              dict(nombre="Sistemas integrables y geometría de trompos",
                   descripcion="Clasificación de los casos integrables del movimiento de un sólido rígido.",
                   objetivo_general="Describir geométricamente las soluciones del trompo de Kovalévskaya.",
                   metodologia="Funciones theta hiperelípticas y métodos de Lax.",
                   resultados_esperados="Un artículo y un curso de posgrado.",
                   bibliografia="Kowalevski, S. (1889). Sur le problème de la rotation d'un corps solide. Acta Math. 12."),
              ["Reobtener la cuarta integral con pares de Lax.", "Visualizar las soluciones."],
              [(f"{periodo}-11", "Curso de posgrado"), (f"{periodo + 1}-05", "Taller internacional")], "enviada")
    return True


# Historial de vínculo de ejemplo (como lo entregaría Recursos Humanos).
HISTORIAL = {
    "sofia.kovalevskaya@instituto.test": [dict(categoria="titular", desde="2012-03-01", hasta=None, jornada=40)],
    "emmy.noether@instituto.test": [dict(categoria="contratado", desde="2018-03-01", hasta="2021-12-31", jornada=40),
                                    dict(categoria="titular", desde="2022-01-01", hasta=None, jornada=40)],
    "alan.turing@instituto.test": [dict(categoria="contratado", desde="2024-08-01", hasta="2026-12-31", jornada=40)],
    "srinivasa.ramanujan@instituto.test": [dict(categoria="invitado", desde="2026-03-01", hasta="2026-12-31",
                                                jornada=20, nota="Estancia de investigación")],
}


def _cargar_vinculos():
    """Reemplaza el vínculo «sin fecha» de las cuentas de ejemplo por su historial. True si lo hizo."""
    hecho = False
    for email, periodos in HISTORIAL.items():
        u = usuarios.por_email(email)
        actuales = vinculos.listar(u["id"]) if u else []
        if u and (not actuales or all(v["fecha_inicio"] is None for v in actuales)):
            vinculos.reemplazar_historial(u["id"], periodos)
            hecho = True
    # Carga horaria contratada del periodo vigente (Ramanujan, invitado, no tiene: participa en
    # proyectos sin carga asignada).
    for email, horas, acts, detalles in (
            ("sofia.kovalevskaya@instituto.test", 160, {"docencia": 64, "investigacion": 64, "gestion": 32},
             {"gestion": "Dirección del Instituto"}),
            ("emmy.noether@instituto.test", 128, {"docencia": 64, "investigacion": 64}, {}),
            ("alan.turing@instituto.test", 64, {"docencia": 32, "extension": 32},
             {"extension": "Olimpiadas de matemática"})):
        u = usuarios.por_email(email)
        v = vinculos.vigente(u["id"]) if u else None
        if v and not vinculos.carga_de(v):
            carga = {"horas": horas, "detalles": detalles,
                     "actividades": {k: acts.get(k, 0) for k in vinculos.ACTIVIDADES}}
            vinculos.editar(v["id"], v["categoria"], v["fecha_inicio"], v["fecha_fin"], nota=v["nota"], carga=carga)
            hecho = True
    return hecho


def _cargar_estudiantes():
    """Estudiante de ejemplo (solo si no hay ninguno): una tesista de licenciatura que dirige Emmy y
    participa en el proyecto IDH. True si la cargó."""
    db = get_db()
    if db.q("SELECT 1 FROM estudiante LIMIT 1"):
        return False
    emmy = usuarios.por_email("emmy.noether@instituto.test")
    algebra = db.q("SELECT id FROM proyecto WHERE codigo = 'IIMAT-IDH-2025-01'")
    if not emmy or not algebra:
        return False
    maria = personas.externo_similar("María", "Quispe") or personas.crear_externo(
        "María", "Quispe", "Carrera de Matemática, UMSA", "Bolivia", emmy["id"])
    estudiantes.agregar(maria["id"], {"nivel": "licenciatura", "desde": "2022", "del_programa": "1"}, emmy["id"])
    tipo = db.q("SELECT id FROM tipo_producto WHERE nombre = 'Tesis dirigida'")[0]["id"]
    d, errores = productos.preparar(dict(tipo_id=str(tipo), titulo="Anillos de invariantes de autómatas finitos",
                                         anio="2026", estado_publicacion="en_preparacion", revision="sin_arbitraje",
                                         medio="Tesis de licenciatura, Carrera de Matemática (UMSA)"),
                                    [f"e:{maria['id']}", f"i:{emmy['id']}"], [])
    assert not errores, errores
    productos.guardar(d, [f"e:{maria['id']}", f"i:{emmy['id']}"], emmy["id"])
    proyectos.agregar_participante(algebra[0]["id"], f"e:{maria['id']}", "tesista", False)
    return True


def _cargar_revistas():
    """Catálogo de ejemplo (solo si está vacío): una revista real verificada y la ficticia de los
    datos de ejemplo, pendiente de verificar. True si lo cargó."""
    db = get_db()
    if db.q("SELECT 1 FROM revista LIMIT 1"):
        return False
    admin = usuarios.por_email(ADMIN["email"])["id"]
    jsl = revistas.crear({"titulo": "Journal of Symbolic Logic", "issn": "0022-4812", "eissn": "1943-5886",
                          "pais": "Estados Unidos", "editorial": "Cambridge University Press", "arbitrada": 1,
                          "acceso_abierto": 0, "url": "https://www.cambridge.org/core/journals/journal-of-symbolic-logic"},
                         admin, verificada=True)
    for indice in ("Web of Science (SCIE)", "Scopus", "MathSciNet", "zbMATH Open"):
        iid = db.q("SELECT id FROM indice WHERE nombre = ?", [indice])[0]["id"]
        revistas.agregar_indexacion(jsl, {"indice_id": iid, "desde": 1990,
                                          "fuente": "Datos de demostración (verifique en la fuente oficial)"}, admin)
    # Ficticia: sin ISSN (no debe coincidir con una revista real).
    revistas.crear({"titulo": "Revista de Álgebra", "pais": "Bolivia", "arbitrada": 1, "acceso_abierto": 1,
                    "nota": "Revista ficticia de los datos de demostración."}, admin)
    return True


def _cargar_lineas() -> bool:
    """Adscripción de ejemplo a las líneas institucionales (solo si nadie se ha adscrito aún)."""
    db = get_db()
    if db.q("SELECT 1 FROM investigador_linea UNION ALL SELECT 1 FROM proyecto_linea LIMIT 1"):
        return False
    por_email = {"emmy.noether@instituto.test": [2], "alan.turing@instituto.test": [4],
                 "sofia.kovalevskaya@instituto.test": [1], "srinivasa.ramanujan@instituto.test": [6]}
    for email, ids in por_email.items():
        u = usuarios.por_email(email)
        if u:
            lineas.adscribir_investigador(u["id"], ids)
    por_proyecto = {"Estructuras algebraicas y computación": [2, 4],
                    "Ecuaciones diferenciales y mecánica del sólido rígido": [1],
                    "Sistemas integrables y geometría de trompos": [1]}
    for nombre, ids in por_proyecto.items():
        for f in db.q("SELECT id FROM proyecto WHERE nombre = ?", [nombre]):
            lineas.fijar_proyecto(f["id"], ids)
            for prop in db.q("SELECT id, copia_enviada FROM propuesta_institucional WHERE proyecto_id = ?",
                             [f["id"]]):
                lineas.fijar_propuesta(prop["id"], ids)
                if prop["copia_enviada"]:  # lo que revisa la administración también las muestra
                    copia = {**json.loads(prop["copia_enviada"]),
                             "lineas": [x["nombre"] for x in lineas.de_propuesta(prop["id"])]}
                    db.execute("UPDATE propuesta_institucional SET copia_enviada = ? WHERE id = ?",
                               [json.dumps(copia, ensure_ascii=False), prop["id"]])
    return True


def _cargar_carga_en_proyectos():
    """Emmy dedica 32 h/mes de su investigación al proyecto institucional que dirige (si aún no tiene)."""
    emmy = usuarios.por_email("emmy.noether@instituto.test")
    algebra = get_db().q("SELECT * FROM proyecto WHERE codigo = 'IIMAT-IDH-2025-01'")
    if not emmy or not algebra:
        return
    part = get_db().q("SELECT id FROM proyecto_participante WHERE proyecto_id = ? AND investigador_id = ?",
                      [algebra[0]["id"], emmy["id"]])
    if part and not carga_proyectos.actual(part[0]["id"]):
        carga_proyectos.asignar(algebra[0]["id"], part[0]["id"], 32, emmy["id"])


def _cargar_docencia() -> bool:
    """Gestiones 2026 (los semestres con las troncales) y docentes de ejemplo en II-2026 (solo si no
    hay gestiones)."""
    if gestiones.listar():
        return False
    por = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    emmy = usuarios.por_email("emmy.noether@instituto.test")
    alan = usuarios.por_email("alan.turing@instituto.test")
    for tipo in ("I", "II"):
        oferta.ofertar_troncales(por[tipo], emmy["id"] if emmy else None)
    ofertadas = {(o["sigla"], o["paralelo"]): o["id"] for o in oferta.listar(por["II"]["id"])}
    # Troncales con docente, un segundo paralelo y una electiva.
    for sigla, paralelo, inscritos, docente in (("MAT-111", "A", 42, emmy), ("MAT-111", "B", 38, alan),
                                                ("MAT-251", "A", 15, emmy), ("MAT-392", "A", 8, None)):
        oid = ofertadas.get((sigla, paralelo))
        if oid:
            get_db().execute("UPDATE oferta SET inscritos = ? WHERE id = ?", [inscritos, oid])
        else:
            oid, _ = oferta.agregar(por["II"]["id"], sigla, paralelo, inscritos, emmy["id"] if emmy else None)
        if oid and docente:
            oferta.asignar(oid, docente["id"], "titular")
    return True


# Clasificación MSC2020 de los productos de ejemplo (el principal primero).
MSC_PRODUCTOS = {
    "Anillos con condición de cadena ascendente y sus ideales primarios": ["13E05", "13C05"],
    "Invariantes algebraicos de máquinas de estados finitos": ["68Q70", "03D05", "13A50"],
    "Morfogénesis y ecuaciones de reacción-difusión": ["35K57", "92C15"],
    "Sobre números computables: notas del seminario": ["03D80"],
}


def _clasificar_productos() -> int:
    """Clasifica los productos de ejemplo que aún no tienen códigos MSC (también en bases anteriores)."""
    n = 0
    for titulo, codigos in MSC_PRODUCTOS.items():
        fila = get_db().q("""SELECT id FROM producto p WHERE titulo = ?
                             AND NOT EXISTS (SELECT 1 FROM producto_msc WHERE producto_id = p.id)""", [titulo])
        if fila:
            msc.guardar_de_producto(fila[0]["id"], codigos)
            n += 1
    return n


def _cargar_preprint() -> bool:
    """Un preprint de Emmy enlazado a su versión publicada (PLAN.md §46), si aún no lo hay."""
    articulo = get_db().q("SELECT id FROM producto WHERE titulo = ?",
                          ["Anillos con condición de cadena ascendente y sus ideales primarios"])
    emmy = usuarios.por_email("emmy.noether@instituto.test")
    if not articulo or not emmy or get_db().q("SELECT 1 FROM producto WHERE publicado_como_id IS NOT NULL"):
        return False
    autores = [f"i:{emmy['id']}"]
    d, errores = productos.preparar(dict(tipo_id=str(_id_tipo("tipo_producto", "Preprint")), anio="2025", mes="9",
                                         titulo="Anillos noetherianos: ideales primarios y cadenas ascendentes",
                                         estado_publicacion="publicado", revision="sin_arbitraje",
                                         medio="arXiv [math.AC]", arxiv_id="2509.04321", msc=["13E05"]), autores, [])
    assert not errores, errores
    pre = productos.guardar(d, autores, emmy["id"], filiaciones=[1])
    assert productos.enlazar_version(pre, articulo[0]["id"]) is None
    return True


def _cargar_perfil(uid: int, datos: dict | None):
    if not datos:
        return
    datos = dict(datos)
    for codigo in datos.pop("areas", []):
        perfiles.agregar_area(uid, codigo)
    for g in datos.pop("grados", []):
        errores = academicos.agregar_grado(uid, g)
        assert not errores, f"Grado de ejemplo no válido: {errores}"
    perfiles.actualizar_campos(uid, **datos)


def main():
    config.CORREO_MODO = "desactivado"  # cargar datos de ejemplo no debe generar avisos
    if "--reset" in sys.argv:
        # También los archivos -wal/-shm: si quedan huérfanos, SQLite corrompe la BD nueva.
        for ruta in (config.DB_PATH, *(config.DB_PATH.with_name(config.DB_PATH.name + s)
                                       for s in ("-wal", "-shm", "-journal"))):
            ruta.unlink(missing_ok=True)
        # Fotos, adjuntos y correos pertenecen a la base borrada: sin esto quedarían huérfanos.
        for carpeta in ("fotos", "adjuntos", "correos"):
            shutil.rmtree(config.DB_PATH.parent / carpeta, ignore_errors=True)
        print(f"Base de datos eliminada: {config.DB_PATH}, con sus fotos, adjuntos y correos "
              "(detenga el servidor antes de --reset)")
    init_db(config.DB_PATH)

    creados = []
    if not usuarios.por_email(ADMIN["email"]):
        usuarios.crear(**ADMIN)
        creados.append((ADMIN["email"], ADMIN["password"], "admin"))
    for inv in INVESTIGADORES:
        if not usuarios.por_email(inv["email"]):
            u = usuarios.crear(password=PASS_TEMPORAL_DEMO, **inv)
            _cargar_perfil(u["id"], PERFILES.get(inv["email"]))
            creados.append((inv["email"], PASS_TEMPORAL_DEMO,
                            "investigador + admin" if inv.get("es_admin") else "investigador"))

    # Bases creadas antes de las categorías: completa las de las cuentas de demostración.
    categorias = 0
    for inv in INVESTIGADORES:
        u = usuarios.con_perfil(usuarios.por_email(inv["email"])["id"])
        if not u["categoria"]:
            perfiles.cambiar_categoria(u["id"], inv["categoria"])
            categorias += 1

    con_vinculos = _cargar_vinculos()
    produccion = _cargar_produccion()
    con_proyectos = _cargar_proyectos()
    con_propuestas = _cargar_institucionales()
    con_revistas = _cargar_revistas()
    con_estudiantes = _cargar_estudiantes()
    con_lineas = _cargar_lineas()
    con_docencia = _cargar_docencia()
    _cargar_carga_en_proyectos()
    _clasificar_productos()
    _cargar_preprint()
    # Internacionalización de ejemplo (idempotente): países normalizados y ámbito de los proyectos.
    personas.completar_paises()
    db = get_db()
    isp = db.q("SELECT id FROM proyecto WHERE codigo = 'ISP-BOL-2025' AND ambito IS NULL")
    if isp and not proyectos.contrapartes(isp[0]["id"]):
        db.execute("UPDATE proyecto SET ambito = 'internacional' WHERE id = ?", [isp[0]["id"]])
        proyectos.agregar_contraparte(isp[0]["id"], "Uppsala University", "Suecia")
    db.execute("UPDATE proyecto SET ambito = 'nacional' WHERE codigo = 'IIMAT-IDH-2025-01' AND ambito IS NULL")
    # Artículos de ejemplo sin revista del catálogo: se vinculan por el nombre de la revista.
    for g in revistas.sin_vincular():
        if g["sugerida"]:
            revistas.vincular([x["id"] for x in g["productos"]], g["sugerida"]["id"])
    # Filiación de ejemplo (solo si nadie la ha declarado aún en estos productos): Emmy firmó su
    # artículo con IIMAT/UMSA y Alan el suyo; Emmy aún no declara la suya en el de Alan (aviso en su inicio).
    db = get_db()
    demo = db.q("""SELECT pa.producto_id, pa.investigador_id, p.titulo FROM producto_autor pa
                   JOIN producto p ON p.id = pa.producto_id WHERE pa.investigador_id IS NOT NULL
                     AND p.titulo IN ('Anillos con condición de cadena ascendente y sus ideales primarios',
                                      'Invariantes algebraicos de máquinas de estados finitos')""")
    if demo and not db.q("""SELECT 1 FROM producto_autor pa JOIN producto p ON p.id = pa.producto_id
                            WHERE pa.filiacion_instituto IS NOT NULL AND p.titulo IN
                            ('Anillos con condición de cadena ascendente y sus ideales primarios',
                             'Invariantes algebraicos de máquinas de estados finitos')"""):
        emmy_id = usuarios.por_email("emmy.noether@instituto.test")["id"]
        for f in demo:
            if not (f["titulo"].startswith("Invariantes") and f["investigador_id"] == emmy_id):
                db.execute("UPDATE producto_autor SET filiacion_instituto = 1 WHERE producto_id = ? AND investigador_id = ?",
                           [f["producto_id"], f["investigador_id"]])
    # Agradecimiento de ejemplo: el artículo de Emmy agradece al proyecto IDH (el de Alan, pendiente,
    # queda sin declarar).
    db.execute("""UPDATE producto_proyecto SET agradece = 1 WHERE agradece IS NULL
                  AND producto_id = (SELECT id FROM producto WHERE titulo =
                                     'Anillos con condición de cadena ascendente y sus ideales primarios')
                  AND proyecto_id = (SELECT id FROM proyecto WHERE codigo = 'IIMAT-IDH-2025-01')""")
    # Bases creadas antes del mes de publicación: el artículo de Emmy es de marzo (el otro de 2026
    # queda sin mes, para ver «por confirmar» en la memoria del periodo 2025–2026).
    get_db().execute("""UPDATE producto SET mes = 3 WHERE doi = '10.5555/demo.2026.001' AND mes IS NULL""")
    # Bases creadas con los ejemplos anteriores (códigos chilenos): pasan a ejemplos de la UMSA.
    get_db().execute("""UPDATE proyecto SET codigo = 'IIMAT-IDH-2025-01', fuente_financiamiento = 'Recursos IDH – UMSA',
                        monto = 150000 WHERE codigo = 'FONDECYT 1260001'""")
    get_db().execute("""UPDATE proyecto SET codigo = 'ISP-BOL-2025',
                        fuente_financiamiento = 'International Science Programme (ISP, Suecia)'
                        WHERE codigo = 'FONDECYT 1250042'""")
    # Bases creadas antes de los tipos de proyecto: el proyecto IDH de ejemplo es institucional.
    tipos = get_db().q("""SELECT id FROM proyecto WHERE codigo = 'IIMAT-IDH-2025-01'
                          AND tipo = 'individual'""")
    if tipos:
        get_db().execute("UPDATE proyecto SET tipo = 'institucional' WHERE id = ?", [tipos[0]["id"]])
    if tipos:
        print("El proyecto de ejemplo IIMAT-IDH-2025-01 quedó como institucional.")
    if categorias and not creados:
        print(f"Categoría asignada a {categorias} cuenta(s) de demostración.")
    if not creados and not produccion and not con_proyectos and not categorias and not tipos and not con_propuestas \
            and not con_vinculos and not con_revistas and not con_estudiantes and not con_lineas \
            and not con_docencia:
        print("No hay nada que agregar: los datos de demostración ya existen.")
        return
    if creados:
        print("Cuentas creadas:")
        for email, pw, rol in creados:
            print(f"  {email:40} {pw:20} {rol}")
    if produccion:
        print("Actividades y productos de ejemplo cargados (Emmy Noether y Alan Turing).")
    if con_vinculos and not creados:
        print("Historial de vínculo de ejemplo cargado (Emmy fue contratada y luego titular, y es docente de la Carrera; Ramanujan es invitado).")
    if con_estudiantes:
        print("Estudiante de ejemplo: María Quispe, tesista de licenciatura dirigida por Emmy.")
    if con_docencia:
        print("Docencia de ejemplo: gestiones 2026 y oferta de II-2026 (una asignatura sin docente).")
    if con_lineas:
        print("Líneas de investigación de ejemplo: investigadores y proyectos adscritos a las líneas del programa.")
    if con_revistas:
        print("Catálogo de revistas de ejemplo: Journal of Symbolic Logic (verificada) y Revista de Álgebra (pendiente).")
    if con_propuestas:
        print("Propuestas institucionales de ejemplo: IIMAT-IDH-2025-01 aceptado (termina el 30 de septiembre) "
              "y una propuesta nueva de Sofía por decidir.")
    if con_proyectos:
        print("Proyectos de ejemplo cargados: Emmy es responsable de uno (con propuestas pendientes "
              "de Alan) y co-investigadora en otro de Sofía.")


if __name__ == "__main__":
    main()
