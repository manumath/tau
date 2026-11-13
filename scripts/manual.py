"""Genera el Manual de usuario de TAU (docs/manual/): capturas de pantalla y PDF con la marca de la Carrera.

    uv run python scripts/manual.py              # base de demostración, capturas y PDF
    uv run python scripts/manual.py --solo-pdf   # arma el PDF con las capturas que ya están en docs/manual/img

- El texto está en docs/manual/capitulos/*.html (un archivo por capítulo, en orden) y el estilo en
  docs/manual/estilo.css. Para corregir el manual se editan esos archivos y se vuelve a ejecutar con --solo-pdf.
- Las capturas se toman sobre una base temporal: los datos de ejemplo de scripts/seed.py más lo que agrega `datos()`
  (estudiantes con cuenta, tutoría, una convocatoria a auxiliaturas, un perfil de grado, un comunicado, una encuesta,
  evidencias, una autoevaluación y una acción de mejora). Todo es ficticio; nunca se usa data/portal.db.
- El PDF lo imprime Chrome (Playwright), como los informes del sistema. Si está `pdftotext`, el índice lleva el
  número de página de cada capítulo (se imprime dos veces: la primera para saber en qué página cae cada uno).

Salida: docs/manual/manual.html (se puede abrir en el navegador) y docs/manual/Manual-de-usuario-TAU.pdf.
"""
import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MANUAL = RAIZ / "docs" / "manual"
IMG = MANUAL / "img"
PDF = MANUAL / "Manual-de-usuario-TAU.pdf"
CLAVE = "Manual-de-usuario-2026"            # solo en la base temporal
ANCHO, ALTO = 1120, 720                     # ventana de las capturas de escritorio
DIRECCION = "admin@instituto.test"          # Ada: administración y las dos direcciones (ve casi todo)
DOCENTE = "emmy.noether@instituto.test"     # Emmy: docente investigadora, tutora y tribunal
ESTUDIANTE = "andrea.limachi@estudiante.test"


# --- Base de demostración -----------------------------------------------------------------------------------------

def datos(ruta: str):
    """Agrega a la base del seed lo que hace falta para ilustrar cada módulo. Se ejecuta en un proceso aparte, con
    PORTAL_DB apuntando a la base temporal."""
    from starlette.testclient import TestClient

    import main
    from app.academico import gestiones
    from app.calidad import autoevaluacion, evidencias, marco, mejora
    from app.comun import estudiantes, permisos, tokens, unidades, usuarios
    from app.comun.db import get_db
    from app.estudiantil import actividad, encuestas, tutoria
    from app.servicios import auxiliaturas as aux
    from app.servicios import grado

    db = get_db()
    uid = lambda email: usuarios.por_email(email)["id"]  # noqa: E731
    ada, emmy, sofia, alan = (uid(e) for e in (DIRECCION, DOCENTE, "sofia.kovalevskaya@instituto.test",
                                              "alan.turing@instituto.test"))
    for rol, sigla in (("direccion_carrera", "CMAT"), ("direccion_instituto", "IIMAT")):
        permisos.asignar(ada, rol, unidades.id_de(sigla))
    usuarios.cambiar_password(emmy, CLAVE, temporal=False)
    db.execute("UPDATE investigador SET perfil_publico = 1 WHERE usuario_id IN (?, ?, ?)", [emmy, sofia, alan])

    # Estudiantes con correo y cuenta (sin contraseña: entran con un enlace).
    def externo(nombres, apellidos):
        return db.q("SELECT id FROM persona_externa WHERE nombres = ? AND apellidos = ?", [nombres, apellidos])[0]["id"]

    cuentas = {}
    for nombres, apellidos in (("Andrea", "Limachi"), ("Carlos", "Mamani"), ("María", "Quispe"), ("Jorge", "Choque"),
                               ("Mateo", "Cruz"), ("Sofía", "Vargas"), ("Hugo", "Mendoza"), ("Paola", "Gutiérrez"),
                               ("Iván", "Salazar")):
        pid = externo(nombres, apellidos)
        correo = f"{nombres}.{apellidos}@estudiante.test".lower().translate(str.maketrans("áéíóú", "aeiou"))
        db.execute("UPDATE persona_externa SET email = ? WHERE id = ?", [correo, pid])
        u = estudiantes.crear_cuenta(pid, ada)
        estudiantes.aceptar_consentimiento(pid)
        cuentas[nombres] = {"externo": pid, "uid": u["id"]}
    andrea = cuentas["Andrea"]

    # Tutoría: Emmy es tutora de la cohorte 2021-I y 2022-I, con una reunión registrada.
    for anio, ciclo in ((2021, "I"), (2022, "I")):
        tutoria.asignar_cohorte(anio, ciclo, emmy, ada)
    hace = lambda dias: (date.today() - timedelta(days=dias)).isoformat()  # noqa: E731
    assert tutoria.registrar(andrea["externo"], emmy, {
        "fecha": hace(12), "tema": "academico", "modalidad": "presencial",
        "resumen": "Revisamos el avance del perfil de grado y el calendario del semestre.",
        "acuerdos": "Entregar el borrador de la metodología en dos semanas."}) == []
    assert tutoria.registrar(cuentas["Carlos"]["externo"], emmy, {"fecha": hace(30), "tema": "vocacional"}) == []

    # Actividad estudiantil: una verificada y otra por verificar.
    a1, err = actividad.crear(andrea["externo"], {
        "tipo": "olimpiada", "titulo": "Olimpiada Boliviana de Matemática Universitaria", "fecha_inicio": hace(200),
        "institucion": "Sociedad Boliviana de Matemática"})
    assert not err, err
    actividad.verificar(a1, ada)
    _, err = actividad.crear(andrea["externo"], {
        "tipo": "congreso", "titulo": "Ponencia en las Jornadas de Matemática de la FCPN", "fecha_inicio": hace(20),
        "institucion": "Facultad de Ciencias Puras y Naturales, UMSA"})
    assert not err, err

    # Auxiliaturas: una convocatoria publicada, con tribunal de dos docentes y dos estudiantes.
    g = gestiones.actual()
    of = db.q("""SELECT o.asignatura_id FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id
                 WHERE o.gestion_id = ? ORDER BY a.sigla LIMIT 1""", [g["id"]])[0]
    ahora = datetime.now()
    x, err = aux.validar({"modalidad": "docencia", "gestion_id": g["id"], "numero": "1",
                          "titulo": f"Auxiliaturas de docencia {gestiones.codigo(g)}",
                          "publicacion": date.today().isoformat(),
                          "cierre": (ahora + timedelta(days=12)).strftime("%Y-%m-%dT18:00"),
                          "examen": (ahora + timedelta(days=20)).strftime("%Y-%m-%dT09:00"),
                          "lugar": "Aula 4 de la Carrera", "resolucion": "Res. HCC 045/2026"}, ["docencia"])
    assert not err, err
    cid = aux.crear(x, ada)
    assert aux.agregar_item(aux.obtener(cid), {"asignatura_id": of["asignatura_id"], "plazas": "2", "horas": "40"}) == []
    assert aux.fijar_tribunal(aux.items(cid)[0], [emmy, sofia], [cuentas["Mateo"]["uid"], cuentas["Sofía"]["uid"]]) == []
    assert aux.publicar(cid) == [], aux.publicar(cid)

    # Proyecto de grado: el perfil de Andrea, con visto bueno de su tutora y tribunal designado.
    tid, err = grado.crear_perfil(andrea["externo"], {
        "titulo": "Coloraciones de grafos y el polinomio cromático $P(G, k)$", "tutor_id": emmy}, ["justificacion"])
    assert not err, err
    textos = {
        "introduccion": "El problema de colorear los vértices de un grafo $G$ con $k$ colores, de modo que dos vértices "
                        "adyacentes no compartan color, nació con el problema de los cuatro colores.",
        "planteamiento": "¿Qué propiedades de $G$ determina su polinomio cromático $P(G, k)$?",
        "objetivo_general": "Estudiar el polinomio cromático y sus raíces en familias de grafos planos.",
        "objetivos_especificos": "Calcular $P(G, k)$ para ruedas y escaleras.\nEstudiar la relación de borrado y "
                                 "contracción.\nImplementar el cálculo y contrastarlo con la teoría.",
        "metodologia": "Revisión bibliográfica, demostraciones y experimentación computacional.",
        "calendario": "Meses 1 a 2: marco teórico. Meses 3 a 5: resultados. Mes 6: redacción.",
        "bibliografia": "@book{diestel,\n  author={R. Diestel}, title={Graph Theory}, year={2017}, publisher={Springer}}",
        "justificacion": "El tema conecta la combinatoria con el álgebra y tiene aplicaciones en asignación de recursos."}
    textos = {k: textos.get(k, "Por desarrollar.") for k in (*grado.OBLIGATORIAS, "justificacion")}
    t = grado.obtener(tid)
    assert grado.guardar(t, {"titulo": t["titulo"], "modalidad": "proyecto_grado", "tutor_id": emmy}, textos,
                         ["justificacion"]) == []
    assert grado.pedir_visto_bueno(grado.obtener(tid)) == []
    grado.responder_tutor(grado.obtener(tid), emmy, True, "")
    assert grado.designar_tribunal(grado.obtener(tid), [sofia, alan], ada) == []

    # Comunicado: un evento con confirmación de asistencia, por las pantallas (como lo haría la Dirección).
    c = TestClient(main.app)
    assert c.post("/login", data={"email": DIRECCION, "password": "Admin-portal-2026"},
                  headers={"HX-Request": "true"}).headers.get("hx-redirect") == "/"
    r = c.post("/servicios/comunicados", follow_redirects=False, data={
        "tipo": "evento", "titulo": "Seminario de la Carrera: simetrías y leyes de conservación",
        "texto": "Charla abierta a estudiantes y docentes. Al terminar habrá un espacio de preguntas.",
        "publica_como": "direccion_carrera", "inicio": (ahora + timedelta(days=6)).strftime("%Y-%m-%dT15:00"),
        "lugar": "Auditorio de la Carrera de Matemática", "confirmar": "1"})
    com = int(r.headers["location"].rsplit("/", 1)[1])
    for grupo in ("cohorte:2021", "cohorte:2022", "docentes"):
        c.post(f"/servicios/comunicados/{com}/convocados/grupo", data={"grupo": grupo})
    assert c.post(f"/servicios/comunicados/{com}/publicar").status_code == 200

    # Encuesta de satisfacción (anónima), abierta y con siete respuestas.
    eid = encuestas.crear_desde_plantilla("satisfaccion", ada)
    invitadas, _, err = encuestas.abrir(eid, ada)
    assert not err and invitadas >= 7, (invitadas, err)
    fichas = [f["token"] for f in db.q("SELECT token FROM invitacion_encuesta WHERE encuesta_id = ? ORDER BY id", [eid])]
    comentarios = ("Más horarios de consulta.", "Las prácticas de laboratorio ayudan mucho.", "Mejorar la biblioteca.",
                   "Más seminarios con docentes invitados.", "Ampliar la oferta de electivas.",
                   "Buen acompañamiento de los tutores.", "Más salas de estudio.")
    for n, ficha in enumerate(fichas[:7]):
        crudo = {}
        for i, q in enumerate(encuestas.preguntas(eid)):
            crudo[q["id"]] = {"escala": [str(3 + (n + i) % 3)], "si_no": ["si" if (n + i) % 4 else "no"],
                              "opcion": [q["opciones"][(n + i) % len(q["opciones"])]] if q["opciones"] else [""],
                              "multiple": q["opciones"][:1 + n % 2], "texto": [comentarios[n]]}[q["tipo"]]
        err = encuestas.responder(ficha, crudo)
        assert not err, err

    # Calidad: dos evidencias, una autoevaluación en curso con juicios y una acción de mejora.
    m = marco.de_unidad(unidades.id_de("CMAT"))
    criterios = evidencias.criterios_del_marco(m["id"])
    for titulo, url, cs in (("Plan de estudios 2017 (Resolución HCU 041/2017)", "https://ejemplo.test/plan-2017", criterios[:2]),
                            ("Reglamento de tutoría de la Carrera", "https://ejemplo.test/tutoria", criterios[2:3])):
        x, err = evidencias.validar({"titulo": titulo, "url": url, "fecha": hace(400),
                                     "criterios": [k["id"] for k in cs]}, m["id"], "enlace")
        assert not err, err
        evidencias.crear(m["id"], "enlace", x, ada)
    hoy = date.today().year
    x, err = autoevaluacion.validar({"nombre": f"Autoevaluación {hoy}", "desde_anio": str(hoy - 2), "hasta_anio": str(hoy - 1)})
    assert not err, err
    aid = autoevaluacion.crear(m["id"], x, ada)
    escala = marco.escala(m["id"])
    juicios = (("Los propósitos están aprobados y difundidos; falta revisarlos con los egresados.",
                "Propósitos aprobados por el Consejo de Carrera.", "No se consulta a egresados ni empleadores.", 2),
               ("La estructura de gobierno funciona y deja actas.", "Consejo de Carrera con reuniones regulares.",
                "Las actas no están digitalizadas.", 3),
               ("El plan de estudios está vigente, con observaciones registradas.", "Plan 2017 documentado.",
                "Observaciones del plan sin resolver.", 2))
    for k, (juicio, fortalezas, debilidades, nivel) in zip(criterios, juicios):
        x, err = autoevaluacion.validar_juicio({"nivel": str(escala[nivel]["valor"]), "juicio": juicio,
                                                "fortalezas": fortalezas, "debilidades": debilidades}, escala)
        assert not err, err
        autoevaluacion.guardar_juicio(aid, k["id"], x, ada)
    x, err = mejora.validar({"titulo": "Consultar los propósitos de la Carrera con egresados y empleadores",
                             "plazo": (date.today() + timedelta(days=150)).isoformat(), "responsable_id": str(sofia),
                             "criterio_id": str(criterios[0]["id"]), "prioridad": "alta", "origen": "autoevaluacion",
                             "debilidad": "No se consulta a egresados ni empleadores.", "autoevaluacion_id": str(aid)},
                            m["id"])
    assert not err, err
    mejora.crear(m["id"], x, ada)

    # Planes (PLAN §65): una reforma en elaboración con la Licenciatura en Matemática copiada (con una asignatura nueva
    # que reemplaza a dos, y una mención) y la Maestría en Matemática vacía.
    from app.academico import equivalencias, malla, menciones, planes as planes_, reformas
    ids = {r["nombre"]: r["id"] for r in db.q("SELECT id, nombre FROM programa")}
    rid, err = reformas.crear(ada, "Plan 2027", "HCU 9/2027", "2027",
                              {ids["Licenciatura en Matemática"]: "copia", ids["Maestría en Matemática"]: "vacio"}, [])
    assert not err, err
    borrador = db.q("SELECT id FROM plan_estudios WHERE reforma_id = ? AND programa_id = ?",
                    [rid, ids["Licenciatura en Matemática"]])[0]["id"]
    vigente = db.q("SELECT id FROM plan_estudios WHERE nombre = 'Plan 2017' AND programa_id = ?",
                   [ids["Licenciatura en Matemática"]])[0]["id"]
    db.execute("""DELETE FROM requisito WHERE plan_asignatura_id IN (SELECT id FROM plan_asignatura WHERE plan_id = ?)
                  AND sigla IN ('MAT-241', 'MAT-242')""", [borrador])         # requisitos que el plan 2017 trae rotos
    por_sigla = {f["sigla"]: f["id"] for f in planes_.asignaturas(borrador) if f["sigla"]}
    for sigla in ("MAT-112", "MAT-122"):
        malla.quitar_fila(borrador, por_sigla[sigla], ada)
    assert not malla.guardar_fila(borrador, None, {"tipo": "obligatoria", "semestre": "1", "sigla": "MAT-190",
                                                  "nombre": "Cálculo en una y varias variables", "horas_teoricas": "6",
                                                  "horas_practicas": "4"}, [], ada)
    ant = {a["sigla"]: a["id"] for a in db.q("SELECT id, sigla FROM asignatura")}
    assert not equivalencias.crear(vigente, borrador, [ant["MAT-112"], ant["MAT-122"]], [ant["MAT-190"]],
                                   "Se fusionan en un solo curso", ada)
    assert not menciones.guardar(borrador, None, {"nombre": "Matemática pura", "semestre_eleccion": "6",
                                                  "descripcion": "Énfasis en álgebra, análisis y topología.",
                                                  "minimo_asignaturas": "3"}, ada)
    pura = menciones.listar(borrador)[0]["id"]
    tardias = [f["id"] for f in planes_.asignaturas(borrador) if f["sigla"] and (f["semestre"] or 0) >= 7][:4]
    assert not menciones.asignar(borrador, pura, {i: "o" for i in tardias}, ada)

    # Gestiones (PLAN §66): I-2027 en planificación, con las troncales y algunos titulares.
    from app.academico import oferta as ofertas_
    plan27 = {g["tipo"]: g for g in gestiones.crear_anio(2027)}["I"]
    ofertas_.ofertar_troncales(plan27, ada)
    for o, u in zip(ofertas_.listar(plan27["id"])[:6], (emmy, sofia, alan, emmy, sofia, alan)):
        ofertas_.asignar(o["id"], u, "titular")

    # Gestiones (PLAN §66): con el semestre activo, un docente reasignado y una materia retirada, para ilustrar los cambios.
    from datetime import date as _date
    from app.academico import cambios, oferta as ofertas
    act = db.q("SELECT * FROM gestion_academica WHERE estado = 'activa' ORDER BY fecha_inicio DESC")
    if act:
        ga = act[0]
        hoy = _date.today().isoformat()
        fecha = hoy if ga["fecha_inicio"] <= hoy <= ga["fecha_fin"] else ga["fecha_inicio"]
        o_con = next((o for o in ofertas.listar(ga["id"]) if o["docentes"]), None)
        o_sin = next((o for o in ofertas.listar(ga["id"]) if not o["docentes"]), None)
        if o_con and fecha > ga["fecha_inicio"]:
            assert not cambios.reasignar_docente(o_con["docentes"][0]["id"], sofia,
                                                 {"fecha": fecha, "motivo": "licencia", "detalle": "Licencia por salud"}, ada)
        if o_sin:
            assert not cambios.retirar_materia(o_sin["id"], {"fecha": fecha, "motivo": "falta_inscritos"}, ada)

    # Enlace de ingreso de la estudiante (como el que le llega por correo).
    Path(ruta).with_suffix(".enlace").write_text(f"/acceso/{tokens.emitir(andrea['uid'], 'acceso')}")


# --- Capturas -----------------------------------------------------------------------------------------------------

# (archivo, quién, ruta, opciones). Opciones: clics (textos en los que hacer clic), movil, alto, completa (página
# entera), abrir (selector de un <details> que se abre antes), y espera (ms).
CAPTURAS = [
    ("ingreso", "nadie", "/login", {}),
    ("ingreso-estudiante", "nadie", "/acceso", {}),
    ("inicio", "direccion", "/", {}),
    ("menu-usuario", "direccion", "/", {"clics": ["button[aria-label^='Cuenta de']"], "recorte": (ANCHO - 400, 0, 400, 440)}),
    ("avisos", "direccion", "/avisos", {"alto": 460}),
    ("buscar", "direccion", "/buscar?q=noether", {"alto": 520}),
    ("inicio-telefono", "docente", "/", {"movil": True}),
    ("menu-telefono", "docente", "/", {"movil": True, "clics": ["button:has-text('Más')"]}),
    ("inicio-docente", "docente", "/", {"alto": 600}),
    ("perfil", "docente", "/perfil", {"alto": 1000}),
    ("productos", "docente", "/productos", {"alto": 640}),
    ("producto-nuevo", "docente", "/productos", {"clics": ["text=Nuevo producto"], "alto": 1000}),
    ("actividades", "docente", "/actividades", {"alto": 480}),
    ("proyectos", "docente", "/proyectos", {"alto": 620}),
    ("proyecto-ficha", "docente", "proyecto", {}),
    ("informes", "direccion", "/informes", {"alto": 620}),
    ("memoria", "direccion", "/informes/memoria", {"alto": 1100}),
    ("cv", "docente", "/informes/cv", {"alto": 1000}),
    ("investigadores", "docente", "/investigadores", {"alto": 560}),
    ("mi-docencia", "docente", "/docencia", {"alto": 1000}),
    ("planes", "direccion", "/docencia/planes?estado=vigente", {"alto": 480}),
    ("plan-ficha", "direccion", "plan", {"alto": 1000}),
    ("planes-elaboracion", "direccion", "/docencia/planes", {"alto": 820}),
    ("reforma-nueva", "direccion", "/docencia/planes/reforma/nueva", {"alto": 1100}),
    ("plan-borrador", "direccion", "plan-borrador", {"alto": 900}),
    ("plan-datos", "direccion", "plan-borrador", {"clics": ["text=Editar datos generales"], "alto": 800}),
    ("malla", "direccion", "malla-borrador", {"alto": 1150}),
    ("malla-fila", "direccion", "malla-borrador", {"clics": ["#semestre-1 button:has-text('Agregar')"], "alto": 900}),
    ("mencion-asignaturas", "direccion", "malla-borrador", {"clics": ["button:has-text('Asignaturas')"], "alto": 900}),
    ("equivalencias", "direccion", "equivalencias-borrador", {"alto": 1000}),
    ("reforma", "direccion", "reforma", {"alto": 520}),
    ("plan-cierre", "direccion", "plan", {"clics": ["text=Iniciar el cierre"], "alto": 700}),
    ("gestiones", "direccion", "/docencia/gestiones", {"alto": 640}),
    ("oferta", "direccion", "oferta-planificacion", {}),
    ("oferta-activa", "direccion", "/docencia/oferta", {"alto": 640}),
    ("cambio-docente", "direccion", "/docencia/oferta", {"clics": ["button[aria-label^='Reasignar a']"], "alto": 760}),
    ("cambios-semestre", "direccion", "cambios", {"alto": 520}),
    ("concluir", "direccion", "/docencia/preparacion?semestre=II-2026", {"clics": ["text=Concluir el semestre"], "alto": 700}),
    ("carga", "direccion", "/docencia/carga", {"alto": 600}),
    ("preparacion", "direccion", "preparacion-planificacion", {"alto": 760}),
    ("vinculo", "direccion", "/admin/usuarios?q=noether", {"clics": ["text=Vínculo"], "alto": 900}),
    ("cohortes", "direccion", "/docencia/cohortes", {"alto": 640}),
    ("encuestas", "direccion", "/docencia/encuestas", {"alto": 480}),
    ("encuesta-resultados", "direccion", "encuesta", {"clics": ["text=Ver resultados"], "alto": 1000}),
    ("tutoria", "direccion", "/docencia/tutoria", {"alto": 640}),
    ("mis-tutorados", "docente", "/tutoria", {"alto": 400}),
    ("egresados", "direccion", "/docencia/egresados", {"alto": 640}),
    ("estudiante-inicio", "estudiante", "/estudiante", {"alto": 1000}),
    ("estudiante-telefono", "estudiante", "/estudiante", {"movil": True}),
    ("estudiante-auxiliaturas", "estudiante", "/estudiante/auxiliaturas", {"alto": 380}),
    ("estudiante-grado", "estudiante", "grado-estudiante", {"alto": 1000}),
    ("estudiante-comunicado", "estudiante", "comunicado-estudiante", {"alto": 460}),
    ("comunicado-ficha", "direccion", "comunicado", {"alto": 640}),
    ("auxiliaturas", "direccion", "convocatoria", {"alto": 1000}),
    ("grado-tribunal", "direccion", "grado", {"alto": 1000}),
    ("marco", "direccion", "/calidad/marco", {}),
    ("indicadores", "direccion", "/calidad/indicadores", {"abrir": "details:has(summary:has-text('Cuerpo académico'))",
                                                          "alto": 1000}),
    ("evidencias", "direccion", "/calidad/evidencias", {"alto": 500}),
    ("autoevaluacion", "direccion", "autoevaluacion", {"alto": 1000}),
    ("mejora", "direccion", "/calidad/mejora", {"alto": 520}),
    ("ficha-estadistica", "direccion", "/calidad/ficha", {"alto": 640}),
    ("calidad-datos", "direccion", "/informes/calidad", {"alto": 640}),
    ("usuarios", "direccion", "/admin/usuarios?q=instituto.test", {"alto": 640}),
    ("roles", "direccion", "/admin/usuarios?q=instituto.test", {"clics": ["text=Roles"]}),
    ("auditoria", "direccion", "/admin/auditoria", {"alto": 560}),
    ("revistas", "direccion", "/admin/revistas", {"alto": 560}),
    ("propuestas", "direccion", "/admin/propuestas", {"alto": 600}),
    ("ia", "direccion", "/ia", {}),
    ("publico", "nadie", "/publico", {"alto": 400}),
]


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _rutas_de_la_base(db: Path) -> dict:
    """Direcciones que dependen de los ids de la base de demostración."""
    import sqlite3
    con = sqlite3.connect(db)
    uno = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    rutas = {
        "proyecto": f"/proyectos/{uno("SELECT id FROM proyecto WHERE codigo = 'IIMAT-IDH-2025-01'")}",
        "plan": f"/docencia/planes/{uno('SELECT MIN(id) FROM plan_estudios')}",
        "oferta-planificacion": f"/docencia/oferta?gestion={uno("SELECT id FROM gestion_academica WHERE anio = 2027 AND tipo = 'I'")}",
        "preparacion-planificacion": f"/docencia/preparacion?semestre={uno("SELECT tipo || '-' || anio FROM gestion_academica WHERE anio = 2027 AND tipo = 'I'")}",
        "cambios": f"/docencia/oferta/{uno("SELECT id FROM gestion_academica WHERE estado = 'activa' ORDER BY fecha_inicio DESC LIMIT 1")}/cambios",
        "plan-borrador": f"/docencia/planes/{uno("SELECT id FROM plan_estudios WHERE estado = 'elaboracion' AND programa_id = (SELECT id FROM programa WHERE nombre = 'Licenciatura en Matemática')")}",
        "malla-borrador": f"/docencia/planes/{uno("SELECT id FROM plan_estudios WHERE estado = 'elaboracion' AND programa_id = (SELECT id FROM programa WHERE nombre = 'Licenciatura en Matemática')")}/malla",
        "equivalencias-borrador": f"/docencia/planes/{uno("SELECT id FROM plan_estudios WHERE estado = 'elaboracion' AND programa_id = (SELECT id FROM programa WHERE nombre = 'Licenciatura en Matemática')")}/equivalencias",
        "reforma": f"/docencia/planes/reforma/{uno("SELECT id FROM reforma_curricular WHERE nombre = 'Plan 2027'")}",
        "encuesta": f"/docencia/encuestas/{uno('SELECT MAX(id) FROM encuesta')}",
        "comunicado": f"/servicios/comunicados/{uno('SELECT MAX(id) FROM comunicado')}",
        "comunicado-estudiante": f"/estudiante/comunicados/{uno('SELECT MAX(id) FROM comunicado')}",
        "convocatoria": f"/servicios/auxiliaturas/{uno('SELECT MAX(id) FROM convocatoria_auxiliatura')}",
        "grado": f"/servicios/grado/{uno('SELECT MAX(id) FROM tramite_grado')}",
        "grado-estudiante": f"/estudiante/grado/{uno('SELECT MAX(id) FROM tramite_grado')}",
        "autoevaluacion": f"/calidad/autoevaluaciones/{uno('SELECT MAX(id) FROM autoevaluacion')}",
    }
    con.close()
    return rutas


def capturar():
    from playwright.sync_api import sync_playwright
    carpeta = Path(tempfile.mkdtemp(prefix="manual-tau-"))
    db = carpeta / "tau.db"
    entorno = {**os.environ, "PORTAL_DB": str(db), "PORTAL_CORREO_MODO": "desactivado",
               "PORTAL_INFORMES_PROGRAMADOS": "0"}
    subprocess.run([sys.executable, "scripts/seed.py"], cwd=RAIZ, env=entorno, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "scripts/manual.py", "--datos", str(db)], cwd=RAIZ, env=entorno, check=True)
    rutas = _rutas_de_la_base(db)
    puerto = _puerto_libre()
    servidor = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(puerto)], cwd=RAIZ,
                                env=entorno, stdout=open(carpeta / "servidor.log", "w"), stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{puerto}"
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f"{url}/login", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        else:
            sys.exit(f"El servidor no arrancó: ver {carpeta / 'servidor.log'}")
        IMG.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CANAL", "chrome") or None)
            sesiones = {}

            def contexto(quien, movil):
                clave = (quien, movil)
                if clave in sesiones:
                    return sesiones[clave]
                ctx = navegador.new_context(viewport={"width": 390, "height": 800} if movil else {"width": ANCHO, "height": ALTO},
                                            device_scale_factor=1.5, color_scheme="light", locale="es-BO")
                pagina = ctx.new_page()
                if quien in ("direccion", "docente"):
                    pagina.goto(f"{url}/login")
                    pagina.fill("input[name=email]", DIRECCION if quien == "direccion" else DOCENTE)
                    pagina.fill("input[name=password]", "Admin-portal-2026" if quien == "direccion" else CLAVE)
                    pagina.click("button[type=submit]")
                    pagina.wait_for_load_state("networkidle")
                    assert "/login" not in pagina.url, f"No se pudo ingresar como {quien}"
                elif quien == "estudiante":
                    if movil:      # el enlace sirve una vez: el teléfono reutiliza la sesión del escritorio
                        ctx.add_cookies(sesiones[("estudiante", False)].context.cookies())
                    else:
                        pagina.goto(url + db.with_suffix(".enlace").read_text())
                        pagina.click("button:has-text('Ingresar')")
                        pagina.wait_for_url("**/estudiante**")
                sesiones[clave] = pagina
                return pagina

            for nombre, quien, ruta, op in CAPTURAS:
                movil = bool(op.get("movil"))
                pagina = contexto(quien, movil)
                if not movil:
                    pagina.set_viewport_size({"width": ANCHO, "height": op.get("alto", ALTO)})
                pagina.goto(url + rutas.get(ruta, ruta))
                pagina.wait_for_load_state("networkidle")
                if op.get("abrir"):
                    pagina.locator(op["abrir"]).first.locator("summary").first.click()
                for selector in op.get("clics", []):
                    pagina.locator(selector).locator("visible=true").first.click(timeout=10000)
                    pagina.wait_for_timeout(700)
                pagina.wait_for_timeout(op.get("espera", 250))
                extra = {}
                if op.get("recorte"):
                    x, y, ancho, alto = op["recorte"]
                    extra["clip"] = {"x": x, "y": y, "width": ancho, "height": alto}
                pagina.screenshot(path=str(IMG / f"{nombre}.png"), full_page=bool(op.get("completa")), **extra)
                print(f"  {nombre}.png")
            navegador.close()
    finally:
        servidor.terminate()
        shutil.rmtree(carpeta, ignore_errors=True)
    _aligerar()


def _aligerar():
    """Reduce el peso de las capturas (paleta de 256 colores: son pantallas de colores planos)."""
    from PIL import Image
    for archivo in sorted(IMG.glob("*.png")):
        im = Image.open(archivo).convert("RGB")
        im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(archivo, optimize=True)


# --- Documento ----------------------------------------------------------------------------------------------------

def _html(paginas: dict | None = None) -> str:
    """Une los capítulos, numera las figuras y arma el índice. `paginas`: {id del capítulo: n.º de página}."""
    capitulos = [c.read_text() for c in sorted((MANUAL / "capitulos").glob("*.html"))]
    cuerpo = "\n".join(capitulos)
    n = 0

    def figura(m):
        archivo, clase, pie = m.group(1), m.group(2) or "", m.group(3).strip()
        if not (IMG / f"{archivo}.png").exists():
            sys.exit(f"Falta la captura img/{archivo}.png (ejecute sin --solo-pdf)")
        return (f'<figure class="captura {clase}"><img src="img/{archivo}.png" alt="{re.sub("<[^>]+>", "", pie)}">'
                f'<figcaption><b>Figura.</b> {pie}</figcaption></figure>')
    cuerpo = re.sub(r'<captura archivo="([\w-]+)"(?: clase="([\w -]+)")?>(.*?)</captura>', figura, cuerpo, flags=re.S)

    def numerar(m):          # capturas y diagramas, en el orden en que aparecen
        nonlocal n
        n += 1
        return f"<b>Figura {n}.</b>"
    cuerpo = re.sub(r"<b>Figura\.</b>", numerar, cuerpo)
    entradas = []

    def apertura(m):
        atributos = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        cid, numero, titulo = atributos["id"], atributos.get("data-numero", ""), atributos["data-titulo"]
        pagina = f'<span class="pagina">{paginas[cid]}</span>' if paginas and cid in paginas else ""
        entradas.append(f'<li><a href="#{cid}"><span class="numero">{numero}</span><span class="titulo">{titulo}</span>'
                        f'<span class="puntos"></span>{pagina}</a></li>')
        rotulo = f"Capítulo {numero}" if numero else atributos.get("data-rotulo", "Manual de usuario")
        resumen = f"<p>{atributos['data-resumen']}</p>" if atributos.get("data-resumen") else ""
        # «§id§» es una marca invisible (del color del fondo): con ella se sabe en qué página cae el capítulo.
        return (f'<section class="capitulo" id="{cid}">\n<header class="apertura"><span class="marca">§{cid}§</span>'
                f'<span class="numero">{rotulo}</span><h1>{titulo}</h1>{resumen}</header>')
    cuerpo = re.sub(r'<section class="capitulo"([^>]*)>', apertura, cuerpo)
    cuerpo = cuerpo.replace("<!-- INDICE -->", "<ol class=\"indice\">" + "\n".join(entradas) + "</ol>")
    cuerpo = cuerpo.replace("{{FECHA}}", _fecha_larga(date.today())).replace("{{ANIO}}", str(date.today().year))
    return ("<!doctype html>\n<html lang=\"es\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<title>TAU · Manual de usuario</title>\n<link rel=\"stylesheet\" href=\"estilo.css\">\n</head>\n<body>\n"
            + cuerpo + "\n</body>\n</html>\n")


def _fecha_larga(d: date) -> str:
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre")
    return f"{d.day} de {meses[d.month - 1]} de {d.year}"


def _imprimir(pagina):
    pagina.goto((MANUAL / "manual.html").as_uri())
    pagina.wait_for_load_state("networkidle")
    pagina.evaluate("document.fonts.ready")
    pagina.pdf(path=str(PDF), prefer_css_page_size=True, print_background=True)


def _paginas_de_los_capitulos() -> dict:
    """{id del capítulo: página}, leyendo en el PDF la marca invisible que lleva cada capítulo («§id§»)."""
    if not shutil.which("pdftotext"):
        return {}
    texto = subprocess.run(["pdftotext", "-layout", str(PDF), "-"], capture_output=True, text=True).stdout
    paginas = {}
    for n, hoja in enumerate(texto.split("\f"), start=1):
        for cid in re.findall(r"§([\w-]+)§", hoja):
            paginas.setdefault(cid, n)
    return paginas


def armar():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CANAL", "chrome") or None)
        pagina = navegador.new_page()
        (MANUAL / "manual.html").write_text(_html())
        _imprimir(pagina)
        paginas = _paginas_de_los_capitulos()
        if paginas:
            (MANUAL / "manual.html").write_text(_html(paginas))
            _imprimir(pagina)
        navegador.close()
    print(f"{PDF.relative_to(RAIZ)}: {PDF.stat().st_size / 1e6:.1f} MB"
          + ("" if paginas else " (sin números de página en el índice: falta pdftotext)"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-pdf", action="store_true", help="no vuelve a tomar las capturas")
    ap.add_argument("--solo-capturas", action="store_true", help="toma las capturas y no arma el PDF")
    ap.add_argument("--datos", metavar="BASE", help=argparse.SUPPRESS)
    args = ap.parse_args()
    sys.path.insert(0, str(RAIZ))
    if args.datos:
        from app.comun.db import init_db
        init_db(args.datos)
        datos(args.datos)
    else:
        if not args.solo_pdf:
            capturar()
        if not args.solo_capturas:
            armar()
