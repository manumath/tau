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
    if g["tipo"] not in aux.GESTIONES_CONVOCABLES:        # las auxiliaturas son de los semestres regulares (PLAN §70)
        g = db.q("SELECT * FROM gestion_academica WHERE tipo IN ('I', 'II') ORDER BY fecha_inicio DESC LIMIT 1")[0]
        if not db.q("SELECT 1 FROM oferta WHERE gestion_id = ? AND asignatura_id = ?", [g["id"], of["asignatura_id"]]):
            db.t.oferta.insert(gestion_id=g["id"], asignatura_id=of["asignatura_id"])
    ahora = datetime.now()
    x, err = aux.validar({"modalidad": "docencia", "gestion_id": g["id"], "numero": "1",
                          "titulo": f"Auxiliaturas de docencia {gestiones.codigo(g)}",
                          "publicacion": date.today().isoformat(),
                          "cierre": (ahora + timedelta(days=12)).strftime("%Y-%m-%dT18:00"),
                          "examen": (ahora + timedelta(days=20)).strftime("%Y-%m-%dT09:00"),
                          "lugar": "Aula 4 de la Carrera", "recepcion_lugar": "Secretaría de la Carrera",
                          "recepcion_horario": "Lunes a viernes, de 9:00 a 12:00 y de 15:00 a 17:00",
                          "resolucion": "Res. HCC 045/2026"}, ["docencia"])
    assert not err, err
    cid = aux.crear(x, ada)
    assert aux.agregar_item(aux.obtener(cid), {"asignatura_id": of["asignatura_id"], "plazas": "2", "horas": "40"}) == []
    assert aux.fijar_tribunal(aux.items(cid)[0], [emmy, sofia], [cuentas["Mateo"]["uid"], cuentas["Sofía"]["uid"]]) == []
    aux.guardar_resolucion_comision(cid, "Res. CC 130/2026", "Res. CF 52/2026")
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

    # Servicios del estudiante (PLAN §67): plan, oportunidades, temas, recursos, orientación, apoyo, evento con inscripción y una
    # encuesta con retorno.
    from app.estudiantil import apoyo, mi_plan, orientacion
    from app.servicios import comunicados as com_
    from app.servicios import oportunidades, recursos, temas
    plan_lic = db.q("""SELECT p.id FROM plan_estudios p JOIN programa pr ON pr.id = p.programa_id
                       WHERE pr.nombre = 'Licenciatura en Matemática' AND p.estado = 'vigente'""")[0]["id"]
    db.execute("UPDATE estudiante SET plan_id = ?", [plan_lic])
    for sigla in ("MAT-111", "MAT-112", "MAT-113", "MAT-114", "MAT-117", "MAT-131"):
        mi_plan.marcar(andrea["externo"], db.q("SELECT id FROM asignatura WHERE sigla = ?", [sigla])[0]["id"], plan_lic)
    db.execute("UPDATE cuenta_estudiante SET comparte_plan_tutor = 1 WHERE externo_id = ?", [andrea["externo"]])
    ada_u, emmy_u = usuarios.por_id(ada), usuarios.por_id(emmy)
    manana = lambda n: (date.today() + timedelta(days=n)).isoformat()  # noqa: E731
    for tipo, titulo, desc, para, cierre in (
            ("beca", "Beca de excelencia académica 2027", "Cubre materiales y transporte para estudiantes con buen desempeño.",
             "estudiantes", manana(25)),
            ("movilidad", "Movilidad estudiantil: semestre en la Universidad Mayor de San Simón", "Un semestre de intercambio con "
             "reconocimiento de materias.", "estudiantes", manana(40)),
            ("empleo", "Analista de datos junior", "Empresa del sector financiero, jornada completa.", "egresados", manana(20))):
        oid, err = oportunidades.crear({"tipo": tipo, "titulo": titulo, "descripcion": desc, "para": para, "cierre": cierre,
                                        "requisitos": "Estar en los últimos semestres de la licenciatura."
                                        if tipo != "empleo" else "Licenciatura en Matemática o afín."}, ada_u)
        assert not err, err
        assert not oportunidades.cambiar_estado(oid, "publicada", ada_u)
    beca = db.q("SELECT id FROM oportunidad WHERE tipo = 'beca'")[0]["id"]
    assert not oportunidades.postular(beca, andrea["externo"], "Me interesa por mi trabajo en el perfil de grado.")
    for titulo, desc in (("Coloraciones de grafos y el polinomio cromático", "Un tema de combinatoria con aplicaciones."),
                         ("Teoría de números computacional", "Algoritmos de factorización y primalidad.")):
        tid_, err = temas.crear({"titulo": titulo, "descripcion": desc, "cupos": "2", "modalidad": "cualquiera"}, emmy_u)
        assert not err, err
        assert not temas.cambiar_estado(tid_, "publicado", emmy_u)
    assert not recursos.crear({"tipo": "guia", "titulo": "Guía de ejercicios de Álgebra I", "descripcion": "Con soluciones al final."},
                              [str(db.q("SELECT id FROM asignatura WHERE sigla = 'MAT-111'")[0]["id"])], emmy_u,
                              (b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", "algebra-guia.pdf"))[1]
    assert not recursos.crear({"tipo": "enlace", "titulo": "Cálculo diferencial en video", "enlace": "https://videos.ejemplo.test/calculo"},
                              [str(db.q("SELECT id FROM asignatura WHERE sigla = 'MAT-112'")[0]["id"])], emmy_u, None)[1]
    for cat, preg, resp in (("Trámites", "¿Dónde pido una constancia de estudios?", "En Kardex, con su registro universitario (RU)."),
                            ("Becas", "¿Cuándo abren las becas?", "Se publican en «Oportunidades» y en el calendario."),
                            ("Grado", "¿Cuántos días tiene el tribunal para revisar mi perfil?", "Quince días hábiles.")):
        assert not orientacion.guardar_pregunta({"categoria": cat, "pregunta": preg, "respuesta": resp}, ada)
    for tipo, nombre, contacto, horario in (("bienestar", "Bienestar universitario", "Edificio central, planta baja", "Lun a vie, 8:00 a 16:00"),
                                            ("psicologia", "Apoyo psicológico de la Facultad", "bienestar@ejemplo.test", "Con cita previa")):
        assert not orientacion.guardar_servicio({"tipo": tipo, "nombre": nombre, "contacto": contacto, "horario": horario}, ada)
    # El evento del comunicado abre inscripción con cupos y certificado.
    db.execute("UPDATE comunicado SET inscripcion = 1, cupos = 30, certificado = 1, horas = 4 WHERE id = ?", [com])
    com_.inscribir(com, andrea["uid"])
    # Un caso de apoyo que abrió la tutora y una reunión que ella programó.
    cid_, err = apoyo.abrir(andrea["externo"], "academico", "Notamos que quiere avanzar con el perfil de grado y conviene organizar el semestre.",
                            emmy_u, "tutor")
    assert not err, err
    assert not apoyo.responder(cid_, "Cuando quiera nos reunimos para organizar el calendario.", emmy_u, False)
    tutoria.solicitar(andrea["externo"], "academico", "Quisiera revisar mi plan del próximo semestre.")
    sol = db.q("SELECT id FROM tutoria_solicitud WHERE externo_id = ?", [andrea["externo"]])[0]["id"]
    assert not tutoria.programar(sol, emmy, (date.today() + timedelta(days=4)).strftime("%Y-%m-%dT10:00"), "Oficina 12, segundo piso")
    # Una consulta del buzón (la Dirección la verá) y otra anónima.
    assert not orientacion.enviar(andrea["externo"], "consulta", "Horarios del laboratorio", "¿A qué hora abre el laboratorio de cómputo?", False)
    assert not orientacion.enviar(andrea["externo"], "sugerencia", "Más salas de estudio", "Faltan salas de estudio en la tarde.", True)
    # Una encuesta de bienestar ya cerrada, con retorno para quienes participaron.
    eid2 = encuestas.crear_desde_plantilla("bienestar", ada)
    assert not encuestas.abrir(eid2, ada)[2]
    for n, ficha in enumerate([f["token"] for f in db.q("SELECT token FROM invitacion_encuesta WHERE encuesta_id = ? ORDER BY id", [eid2])][:6]):
        crudo = {}
        for i, q in enumerate(encuestas.preguntas(eid2)):
            crudo[q["id"]] = {"escala": [str(3 + (n + i) % 3)], "si_no": ["si"],
                              "opcion": [q["opciones"][(n + i) % len(q["opciones"])]] if q["opciones"] else [""],
                              "multiple": q["opciones"][:1], "texto": ["Todo bien en general."]}[q["tipo"]]
        assert not encuestas.responder(ficha, crudo)
    assert encuestas.cerrar(eid2, ada)
    assert not encuestas.guardar_retorno(eid2, "La mayoría se siente acompañada, pero pide más salas de estudio y horarios de consulta.",
                                        "Habilitaremos una sala de estudio en la tarde y publicaremos los horarios de consulta de cada docente.")
    assert not encuestas.publicar_retorno(eid2)

    # Servicios del docente (PLAN §68): una lista de curso, un programa publicado, preferencias, una evaluación cerrada con resultados y
    # un trabajo de grado concluido para certificar.
    from app.academico import evaluacion, listas, preferencias, programas
    from app.academico import oferta as ofertas_
    mias = ofertas_.materias_de(emmy, g["id"])
    sigla0 = mias[0]["sigla"]
    asig0 = db.q("SELECT id FROM asignatura WHERE sigla = ?", [sigla0])[0]["id"]
    estudiantes_lista = "".join(f"{sigla0},{mias[0]['paralelo']},{ru},{ap},{nom},\n" for ru, ap, nom in (
        ("8101", "Limachi", "Andrea"), ("8102", "Mamani", "Carlos"), ("8103", "Quispe", "María"), ("8104", "Choque", "Jorge")))
    assert not listas.cargar(("sigla,paralelo,ru,apellidos,nombres,correo\n" + estudiantes_lista).encode(), g["id"], ada)[1]
    assert not programas.guardar(asig0, g["id"], emmy, {
        "objetivos": "Que el estudiante domine los conceptos básicos del curso y los aplique a problemas concretos.",
        "contenido": "1. Fundamentos\n2. Técnicas principales\n3. Aplicaciones", "metodologia": "Clases teóricas y sesiones de práctica.",
        "evaluacion": "Dos exámenes parciales (60 %) y un examen final (40 %).", "bibliografia": "Apostol, T. Calculus. Reverté."})
    assert not programas.publicar(asig0, g["id"], emmy)
    sig = gestiones.crear(g["anio"] + 1, "I", ada)[0] or gestiones.por_codigo(f"I-{g['anio'] + 1}")
    assert not preferencias.guardar(sig, emmy, {asig0: ("prefiere", "La dicté tres veces")}, ["lun-noche", "mar-noche"],
                                    "Prefiero las clases por la mañana.")
    pasada = gestiones.crear(g["anio"] - 1, "II", ada, concluida=True)[0] or gestiones.por_codigo(f"II-{g['anio'] - 1}")
    db.execute("UPDATE gestion_academica SET estado = 'concluida' WHERE id = ?", [pasada["id"]])
    po = next((o["id"] for o in ofertas_.listar(pasada["id"]) if o["sigla"] == sigla0 and o["paralelo"] == "A"), None)
    if po is None:
        po, _ = ofertas_.agregar(pasada["id"], sigla0, "A", "30", ada)
    assert not ofertas_.fijar_titular(po, emmy)
    hoy_ = date.today()
    eid, err = evaluacion.crear(pasada["id"], (hoy_ - timedelta(days=10)).isoformat(), (hoy_ + timedelta(days=5)).isoformat(), ada)
    assert not err, err
    assert not evaluacion.anunciar(eid, ada)
    db.execute("UPDATE evaluacion_docente SET anunciada_en = ? WHERE id = ?", [(hoy_ - timedelta(days=12)).isoformat() + " 09:00:00", eid])
    assert not evaluacion.abrir(eid, ada)
    for n in range(9):
        r = db.t.evaluacion_respuesta.insert(evaluacion_id=eid, oferta_id=po)
        for k, (clave, _t) in enumerate(evaluacion.CRITERIOS):
            db.execute("INSERT INTO evaluacion_valor (respuesta_id, criterio, valor) VALUES (?, ?, ?)", [r["id"], clave, 3 + (n + k) % 3])
    assert not evaluacion.cerrar(eid, ada)
    assert not evaluacion.guardar_retorno(eid, "Reforzaremos las sesiones de práctica y publicaremos los programas antes del semestre.")
    assert not evaluacion.publicar_retorno(eid, ada)
    evaluacion.registrar_consulta(eid, emmy, ada)
    camila = db.t.persona_externa.insert(nombres="Camila", apellidos="Rojas", email="camila.rojas@estudiante.test")["id"]
    db.t.tramite_grado.insert(externo_id=camila, tipo="perfil", titulo="Grupos de Lie y simetrías de ecuaciones diferenciales", tutor_id=emmy,
                              estado="aprobado", enviado_en=f"{hoy_.year - 1}-09-15 10:00:00")

    # Servicios del investigador (PLAN §69): declaraciones de acceso abierto de dos productos de Emmy (el otro queda sin declarar,
    # para que «Mis pendientes» lo pida).
    from app.investigacion import acceso_abierto as aa
    modelos = [dict(texto="abierto", enlace="https://revista.ejemplo.test/articulo", licencia="cc_by", datos="publicados",
                    datos_enlace="https://zenodo.ejemplo.test/registro/1"),
               dict(texto="embargo", embargo_hasta=(hoy_ + timedelta(days=60)).isoformat())]     # el tercer producto queda sin declarar
    for f, d in zip(aa.de_investigador(emmy), modelos):
        valores, errores = aa.validar(d)
        assert not errores, errores
        aa.guardar(f["id"], valores, emmy)

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
    ("docente-pendientes", "docente", "/docencia/pendientes", {"alto": 560}),
    ("docente-calendario", "docente", "/docencia/calendario", {"alto": 560}),
    ("docente-preferencias", "docente", "/docencia/preferencias", {"alto": 760}),
    ("docente-programas", "docente", "/docencia/programas", {"alto": 460}),
    ("docente-listas", "docente", "/docencia/listas", {"alto": 460}),
    ("docente-lista", "docente", "lista-curso", {"alto": 560}),
    ("docente-evaluacion", "docente", "/docencia/evaluacion", {"alto": 760}),
    ("docente-resultados", "docente", "resultados-evaluacion", {"alto": 1000}),
    ("docente-historial", "docente", "/docencia/historial", {"alto": 900}),
    ("docente-certificado", "docente", "certificado", {"alto": 620}),
    ("inv-pendientes", "docente", "/investigacion/pendientes", {"alto": 640}),
    ("inv-calendario", "docente", "/investigacion/calendario", {"alto": 560}),
    ("inv-acceso", "docente", "/investigacion/acceso-abierto", {"alto": 900}),
    ("inv-acceso-formulario", "docente", "/investigacion/acceso-abierto", {"clics": ["button:has-text('Declarar')"], "alto": 1000}),
    ("inv-colaboraciones", "docente", "/investigacion/coautores", {"alto": 1000}),
    ("inv-colaborador", "docente", "colaborador", {"alto": 620}),
    ("preferencias-personal", "direccion", "/docencia/preferencias/todas", {"alto": 560}),
    ("programas-cobertura", "direccion", "/docencia/programas/cobertura", {"alto": 560}),
    ("evaluacion-gestion", "direccion", "/docencia/evaluacion/gestion", {"alto": 900}),
    ("listas-cargar", "direccion", "/docencia/listas/cargar", {"alto": 640}),
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
    ("estudiante-comunicado", "estudiante", "comunicado-estudiante", {"alto": 760}),
    ("mi-plan", "estudiante", "/estudiante/plan", {"alto": 1000}),
    ("calendario", "estudiante", "/estudiante/calendario", {"alto": 760}),
    ("mi-tutoria", "estudiante", "/estudiante/tutoria", {"alto": 820}),
    ("apoyo", "estudiante", "/estudiante/apoyo", {"alto": 900}),
    ("biblioteca", "estudiante", "/estudiante/biblioteca", {"alto": 620}),
    ("orientacion", "estudiante", "/estudiante/orientacion", {"alto": 900}),
    ("buzon", "estudiante", "/estudiante/buzon", {"alto": 860}),
    ("oportunidades", "estudiante", "/estudiante/oportunidades", {"alto": 640}),
    ("oportunidad", "estudiante", "oportunidad-beca", {"alto": 760}),
    ("temas", "estudiante", "/estudiante/temas", {"alto": 640}),
    ("estudiante-encuestas", "estudiante", "/estudiante/encuestas", {"alto": 900}),
    ("oportunidades-personal", "direccion", "/servicios/oportunidades", {"alto": 560}),
    ("temas-personal", "docente", "/servicios/temas", {"alto": 480}),
    ("recursos-personal", "docente", "/servicios/recursos", {"alto": 480}),
    ("buzon-personal", "direccion", "/servicios/buzon", {"alto": 520}),
    ("apoyo-personal", "direccion", "/apoyo", {"alto": 480}),
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
        "oportunidad-beca": f"/estudiante/oportunidades/{uno("SELECT id FROM oportunidad WHERE tipo = 'beca'")}",
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
        "lista-curso": f"/docencia/listas/{uno('SELECT oferta_id FROM lista_curso LIMIT 1')}",
        "resultados-evaluacion": f"/docencia/evaluacion/{uno('SELECT id FROM evaluacion_docente')}/docente/{uno("SELECT docente_id FROM evaluacion_consulta LIMIT 1")}",
        "certificado": f"/docencia/certificados/tutor_grado/{uno("SELECT id FROM tramite_grado WHERE estado = 'aprobado'")}",
        "colaborador": f"/investigacion/coautores?con=e:{uno("SELECT externo_id FROM producto_autor WHERE externo_id IS NOT NULL AND producto_id IN (SELECT producto_id FROM producto_autor WHERE investigador_id = (SELECT id FROM usuario WHERE email = 'emmy.noether@instituto.test')) GROUP BY externo_id ORDER BY COUNT(*) DESC LIMIT 1")}",
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
