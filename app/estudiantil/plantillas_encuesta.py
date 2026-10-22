"""Encuestas de partida (PLAN §49 y §50). Son borradores: la Dirección las ajusta antes de abrirlas.
Las preguntas de escala se redactan como afirmaciones (1 = totalmente en desacuerdo, 5 = totalmente de acuerdo)."""

E, S, OP, M, T = "escala", "si_no", "opcion", "multiple", "texto"

PLANTILLAS = {
    "satisfaccion": {
        "titulo": "Satisfacción estudiantil", "tipo": "satisfaccion", "anonima": True, "publico": "estudiantes",
        "descripcion": "Queremos conocer cómo valora su formación en la Carrera para mejorarla. Es anónima.",
        "preguntas": [
            ("Las clases de los docentes de la Carrera son claras y están bien organizadas.", E, None),
            ("El plan de estudios es coherente y las materias se articulan entre sí.", E, None),
            ("Puedo consultar a mis docentes fuera de clase cuando lo necesito.", E, None),
            ("Los laboratorios, la biblioteca y los espacios de estudio son adecuados.", E, None),
            ("Recibo orientación académica suficiente (tutoría, información sobre trámites y opciones).", E, None),
            ("Tengo oportunidades de participar en investigación, ayudantías o actividades científicas.", E, None),
            ("La gestión administrativa de la Carrera responde con rapidez a mis solicitudes.", E, None),
            ("En general, estoy satisfecho(a) con mi formación en la Carrera.", E, None),
            ("¿Recomendaría la Carrera a otra persona interesada en la matemática?", S, None),
            ("¿Qué es lo que más debería mejorar la Carrera?", T, None),
        ]},
    "bienestar": {
        "titulo": "Clima y bienestar estudiantil", "tipo": "bienestar", "anonima": True, "publico": "estudiantes",
        "descripcion": "Nos interesa saber cómo se siente en la Carrera y qué dificulta sus estudios. Es anónima.",
        "preguntas": [
            ("Siento que pertenezco a la comunidad de la Carrera.", E, None),
            ("El trato entre estudiantes, docentes y administrativos es respetuoso.", E, None),
            ("Mi carga de trabajo académico es manejable.", E, None),
            ("Sé a quién acudir si tengo un problema personal o académico.", E, None),
            ("Este semestre, ¿presenció o sufrió algún trato discriminatorio o acoso en la Carrera?", S, None),
            ("¿Qué dificultades afectan sus estudios?", M, ["Económicas", "Laborales", "De salud", "Familiares",
                                                           "De transporte o distancia", "Académicas", "Ninguna"]),
            ("¿Cuánto tiempo semanal dedica a trabajar fuera de la universidad?", OP,
             ["No trabajo", "Hasta 10 horas", "De 11 a 20 horas", "De 21 a 30 horas", "Más de 30 horas"]),
            ("¿Qué apoyo le ayudaría más?", T, None),
        ]},
    "abandono": {
        "titulo": "Permanencia y causas de abandono", "tipo": "abandono", "anonima": True, "publico": "estudiantes",
        "descripcion": "Para apoyar la permanencia en la Carrera, queremos entender qué la dificulta. Es anónima.",
        "preguntas": [
            ("¿Ha pensado en dejar la Carrera?", OP, ["No", "Alguna vez", "Con frecuencia", "Estoy por hacerlo"]),
            ("Si lo ha pensado, ¿por qué motivos?", M, ["Dificultad académica", "Falta de dinero", "Trabajo",
                                                       "Motivos familiares o de salud", "La Carrera no es lo que esperaba",
                                                       "Prefiero otra carrera", "Falta de apoyo o de orientación",
                                                       "Otro"]),
            ("Me siento acompañado(a) por la Carrera en mis dificultades.", E, None),
            ("¿Qué cambio le ayudaría a seguir estudiando?", T, None),
        ]},
    "egresados": {
        "titulo": "Seguimiento de egresados", "tipo": "egresados", "anonima": False, "publico": "egresados",
        "descripcion": "Queremos saber cómo le va después de la Carrera y qué tanto le sirvió su formación.",
        "preguntas": [
            ("Situación actual", OP, ["Trabajo en mi área", "Trabajo en otra área", "Estudio un posgrado",
                                    "Trabajo y estudio", "Busco trabajo", "Otra"], "situacion"),
            ("Sector donde trabaja", OP, ["Docencia", "Investigación", "Sector público", "Sector privado o empresa",
                                        "Independiente", "No trabajo"], "sector"),
            ("¿Cuánto tardó en conseguir su primer empleo después de egresar?", OP,
             ["Ya trabajaba", "Menos de 6 meses", "De 6 meses a 1 año", "Más de 1 año", "Aún no lo consigo"], "primer_empleo"),
            ("Lo que aprendí en la Carrera me sirve en mi trabajo o estudios actuales.", E, None, "utilidad"),
            ("¿Cursó o cursa un posgrado?", OP, ["No", "Sí, en Bolivia", "Sí, en el extranjero"], "posgrado"),
            ("Ciudad y país donde vive", T, None, "ubicacion"),
            ("En general, estoy satisfecho(a) con la formación que recibí.", E, None, "satisfaccion"),
            ("¿Qué debería cambiar la Carrera para formar mejor?", T, None),
        ]},
    "perfil_egreso": {
        "titulo": "Logro del perfil de egreso", "tipo": "perfil_egreso", "anonima": False, "publico": "egresados",
        "descripcion": "Valore en qué medida la Carrera le permitió desarrollar cada competencia. "
                       "Ajuste esta lista al perfil de egreso vigente antes de abrir la encuesta.",
        "preguntas": [
            ("La Carrera me permitió razonar con rigor y demostrar resultados matemáticos.", E, None),
            ("Puedo modelar y resolver problemas de otras áreas con herramientas matemáticas.", E, None),
            ("Puedo programar y usar herramientas computacionales para hacer matemática.", E, None),
            ("Puedo comunicar ideas matemáticas por escrito y oralmente.", E, None),
            ("Puedo aprender por mi cuenta temas nuevos y leer literatura científica.", E, None),
            ("Puedo trabajar en equipos con personas de otras disciplinas.", E, None),
            ("Actúo con ética profesional y responsabilidad social.", E, None),
        ]},
}
