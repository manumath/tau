"""Carga datos de demostración.

    uv run python scripts/seed.py            # agrega lo que falte
    uv run python scripts/seed.py --reset    # borra la BD y la recrea

Las contraseñas de demostración son fijas para poder probar el portal; en
producción las cuentas se crean desde Administración → Usuarios.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import actividades, config, perfiles, personas, productos, proyectos, usuarios  # noqa: E402
from app.db import get_db  # noqa: E402
from app.db import init_db  # noqa: E402

ADMIN = dict(email="admin@instituto.test", nombres="Ada", apellidos="Administradora",
             password="Admin-portal-2026", es_admin=True, es_investigador=False,
             debe_cambiar_pass=False)
INVESTIGADORES = [
    # Contraseña temporal común: el portal obliga a cambiarla en el primer ingreso.
    dict(email="sofia.kovalevskaya@instituto.test", nombres="Sofía", apellidos="Kovalévskaya",
         es_admin=True),
    dict(email="emmy.noether@instituto.test", nombres="Emmy", apellidos="Noether"),
    dict(email="alan.turing@instituto.test", nombres="Alan", apellidos="Turing"),
    dict(email="srinivasa.ramanujan@instituto.test", nombres="Srinivasa", apellidos="Ramanujan"),
]
PASS_TEMPORAL_DEMO = "Temporal-2026"

# Perfiles de ejemplo (el de Ramanujan queda vacío para ver un perfil por completar).
# El ORCID es el de Josiah Carberry, investigador ficticio que ORCID usa para pruebas.
PERFILES = {
    "sofia.kovalevskaya@instituto.test": dict(
        grado="Doctorado", cargo="Investigador(a) titular", unidad="Grupo de Ecuaciones Diferenciales",
        areas=["35-XX", "70E17", "35Q35"],
        bio="Estudio el movimiento de un cuerpo rígido alrededor de un punto fijo y la existencia "
            "de soluciones analíticas de ecuaciones en derivadas parciales."),
    "emmy.noether@instituto.test": dict(
        grado="Doctorado", cargo="Investigador(a) titular", unidad="Grupo de Álgebra",
        zbmath_id="noether.emmy", areas=["13-XX", "13E05", "16-XX", "17-XX"],
        bio="Trabajo en álgebra conmutativa y no conmutativa: anillos que satisfacen la condición "
            "de cadena ascendente, $I_1 \\subseteq I_2 \\subseteq \\cdots$, y teoría de ideales.\n\n"
            "También me interesan las relaciones entre simetrías y leyes de conservación:\n"
            "$$\\frac{d}{dt}\\left(\\frac{\\partial L}{\\partial \\dot q}\\,\\delta q\\right) = 0.$$"),
    "alan.turing@instituto.test": dict(
        grado="Doctorado", cargo="Investigador(a) asociado(a)", unidad="Grupo de Lógica y Computación",
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
             anio="2026", medio="Revista de Álgebra", volumen="83", numero="2", paginas="24–66",
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
    """Dos proyectos de ejemplo con vínculos aprobados, pendientes y rechazados."""
    if get_db().q("SELECT 1 FROM proyecto LIMIT 1") or not get_db().q("SELECT 1 FROM producto LIMIT 1"):
        return False
    uid = {u["email"].split(".")[0]: u["id"] for u in usuarios.listar()}
    emmy, alan, sofia, srini, admin = (uid["emmy"], uid["alan"], uid["sofia"], uid["srinivasa"],
                                       usuarios.por_email(ADMIN["email"])["id"])
    weyl = get_db().q("SELECT id FROM persona_externa WHERE apellidos = 'Weyl'")[0]["id"]

    def id_de(tabla, titulo):
        return get_db().q(f"SELECT id FROM {tabla} WHERE titulo = ?", [titulo])[0]["id"]

    base = dict(descripcion=None, objetivo_general=None, fuente_financiamiento=None, monto=None,
                fecha_fin=None)
    algebra = proyectos.crear({**base, "codigo": "FONDECYT 1260001", "estado": "vigente",
                               "nombre": "Estructuras algebraicas y computación",
                               "fecha_inicio": "2026-03-01", "fecha_fin": "2029-02-28",
                               "fuente_financiamiento": "FONDECYT Regular", "monto": 180000000,
                               "descripcion": "Estudio de invariantes algebraicos de modelos de cómputo "
                                              "y de anillos noetherianos asociados.",
                               "objetivo_general": "Caracterizar algebraicamente clases de máquinas de "
                                                   "estados mediante sus anillos de invariantes."},
                              emmy, admin)
    for texto in ("Construir el anillo de invariantes de una máquina de estados finitos.",
                  "Determinar cuándo dicho anillo es noetheriano.",
                  "Formar a un estudiante de doctorado en la línea."):
        proyectos.agregar_objetivo(algebra, texto)
    proyectos.agregar_participante(algebra, f"i:{alan}", "co_investigador", True)
    proyectos.agregar_participante(algebra, f"i:{srini}", "tesista", True)
    proyectos.agregar_participante(algebra, f"e:{weyl}", "colaborador", True)

    rigido = proyectos.crear({**base, "codigo": "FONDECYT 1250042", "estado": "vigente",
                              "nombre": "Ecuaciones diferenciales y mecánica del sólido rígido",
                              "fecha_inicio": "2025-03-01", "fecha_fin": "2028-02-29"}, sofia, admin)
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
                       "Es de 2025, anterior al inicio del proyecto: no corresponde incluirlo.")
    return True


def _cargar_perfil(uid: int, datos: dict | None):
    if not datos:
        return
    datos = dict(datos)
    for codigo in datos.pop("areas", []):
        perfiles.agregar_area(uid, codigo)
    perfiles.actualizar_campos(uid, **datos)


def main():
    if "--reset" in sys.argv:
        # También los archivos -wal/-shm: si quedan huérfanos, SQLite corrompe la BD nueva.
        for ruta in (config.DB_PATH, *(config.DB_PATH.with_name(config.DB_PATH.name + s)
                                       for s in ("-wal", "-shm", "-journal"))):
            ruta.unlink(missing_ok=True)
        print(f"Base de datos eliminada: {config.DB_PATH} (detenga el servidor antes de --reset)")
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

    produccion = _cargar_produccion()
    con_proyectos = _cargar_proyectos()
    if not creados and not produccion and not con_proyectos:
        print("No hay nada que agregar: los datos de demostración ya existen.")
        return
    if creados:
        print("Cuentas creadas:")
        for email, pw, rol in creados:
            print(f"  {email:40} {pw:20} {rol}")
    if produccion:
        print("Actividades y productos de ejemplo cargados (Emmy Noether y Alan Turing).")
    if con_proyectos:
        print("Proyectos de ejemplo cargados: Emmy es responsable de uno (con propuestas pendientes "
              "de Alan) y co-investigadora en otro de Sofía.")


if __name__ == "__main__":
    main()
