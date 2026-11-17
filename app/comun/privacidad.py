"""Qué datos personales guarda el sistema, para qué, quién los ve y cuánto se conservan (PLAN §72, etapa 8; acción A15.2).

Una sola tabla, `TRATAMIENTOS`, alimenta la página pública `/publico/privacidad` y el aviso breve (`layout.aviso_privacidad`) que va
sobre el botón de enviar de cada formulario que pide datos personales: así el aviso y la página no se contradicen. Si cambia
una regla de privacidad (CLAUDE.md, PLAN §49, §50, §58, §67 a §69), cambie aquí el texto en el mismo commit.

`FORMULARIOS` lista los formularios que deben llevar el aviso; `tests/test_privacidad.py` lo exige.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Tratamiento:
    titulo: str
    datos: str
    finalidad: str
    quien_ve: str
    conservacion: str
    aviso: str          # una frase para el formulario: lo esencial de lo anterior


TRATAMIENTOS: dict[str, Tratamiento] = {
    "estudiantes": Tratamiento(
        "Seguimiento de estudiantes",
        "Registro universitario, nombres, correo, sexo, edad al ingresar, cohorte, estado y fechas de egreso y titulación, "
        "que llegan del sistema de Seguimiento Académico, y la actividad que usted declara (ayudantías, olimpiadas, becas, "
        "movilidad y otras) con su evidencia. No se guardan sus materias, sus notas, su fecha de nacimiento ni su carnet.",
        "El seguimiento interno de la Carrera y, sin nombres, las cifras de la evaluación de la calidad.",
        "Usted. La Dirección de Carrera, la Coordinación académica y Gestión de datos ven sus datos individuales; la Comisión "
        "de calidad ve cifras.",
        "Mientras la Carrera hace el seguimiento de su cohorte. Su actividad declarada la corrige o la elimina usted cuando "
        "quiera.",
        "Sus datos se usan para el seguimiento interno de la Carrera y, sin su nombre, en las cifras de calidad; los ven la "
        "Dirección de Carrera, la Coordinación académica y Gestión de datos."),
    "encuestas": Tratamiento(
        "Encuestas",
        "Sus respuestas. En una encuesta anónima no se guarda quién respondió ni la hora; en las demás, la respuesta queda "
        "con su nombre.",
        "Conocer la opinión de estudiantes, egresados, académicos y empleadores para mejorar la Carrera.",
        "La Dirección de Carrera y la Coordinación académica ven los resultados. De una encuesta anónima solo se muestran "
        "resultados con 5 respuestas o más, y las respuestas abiertas nunca se devuelven a quienes respondieron.",
        "El enlace personal se borra al responder o al cerrarse la encuesta; las respuestas se conservan con la encuesta.",
        "Sus respuestas las ven la Dirección de Carrera y la Coordinación académica; si la encuesta es anónima, no se guarda "
        "quién respondió y solo se muestran resultados con 5 respuestas o más."),
    "evaluacion_docente": Tratamiento(
        "Evaluación docente",
        "Sus respuestas sobre cada docente y asignatura, sin su nombre ni la hora. El sistema solo anota que usted ya "
        "participó, sin enlazarlo con la respuesta.",
        "Que cada docente y la Dirección conozcan la opinión de los estudiantes para mejorar la enseñanza.",
        "El docente y la Dirección de Carrera ven resultados solo con 5 respuestas o más; toda consulta de resultados "
        "ajenos queda registrada.",
        "Las respuestas se conservan con la evaluación de cada gestión.",
        "Es anónima: su respuesta no se enlaza con su nombre ni guarda la hora, y los resultados solo se muestran con 5 "
        "respuestas o más."),
    "buzon": Tratamiento(
        "Buzón de consultas, reclamos y sugerencias",
        "El tipo, el asunto y el mensaje, con su nombre. Si lo envía como anónimo, no se guarda su cuenta ni la hora, solo "
        "el día.",
        "Atender su consulta, reclamo o sugerencia.",
        "La Dirección de Carrera y la Coordinación académica.",
        "Se conserva con su respuesta.",
        "Su mensaje lo leen la Dirección de Carrera y la Coordinación académica; si lo envía como anónimo, no se guarda su "
        "cuenta ni la hora."),
    "apoyo": Tratamiento(
        "Apoyo estudiantil y tutoría",
        "Las señales de apoyo se calculan al momento y no se guardan. Un caso de apoyo guarda el motivo y su seguimiento; "
        "las notas de las reuniones de tutoría guardan lo que escribe su tutor.",
        "Acompañarle a tiempo durante la carrera.",
        "Las señales, solo usted. Los casos, la Dirección de Carrera. Las notas de tutoría, su tutor y la Dirección de "
        "Carrera (cada consulta queda registrada); nunca van a informes ni a exportaciones.",
        "Un caso vence a los seis meses si no se renueva.",
        "Las señales solo las ve usted; las notas de tutoría, su tutor y la Dirección de Carrera."),
    "auxiliaturas": Tratamiento(
        "Concursos de auxiliatura",
        "Su postulación, los documentos que adjunta y las calificaciones de la comisión y del tribunal.",
        "El concurso de méritos y examen que establece el reglamento de auxiliares académicos.",
        "La Dirección de Carrera, la Coordinación académica y los miembros de la comisión y del tribunal de esa "
        "convocatoria.",
        "Se conservan con la convocatoria, como respaldo del concurso.",
        "Su postulación y sus documentos los ven la Dirección de Carrera, la Coordinación académica y la comisión y el "
        "tribunal de la convocatoria."),
    "oportunidades": Tratamiento(
        "Becas, movilidad, pasantías y empleo",
        "Su postulación y el mensaje que escriba.",
        "Seleccionar a quienes postulan a la oportunidad.",
        "La Dirección de Carrera y la Coordinación académica.",
        "Se conservan con la convocatoria; puede retirar su postulación mientras está en curso.",
        "Su postulación y su mensaje los ven la Dirección de Carrera y la Coordinación académica."),
    "directorio": Tratamiento(
        "Directorio de egresados",
        "Ocupación, institución, ciudad y país, áreas de trabajo y lo que puede ofrecer a los estudiantes.",
        "Que los estudiantes encuentren egresados que les orienten.",
        "Solo dentro del sistema: estudiantes y personal de la Carrera, y solo si usted marca «Quiero figurar». Su correo se "
        "comparte únicamente con quien usted acepte ayudar.",
        "Mientras figure en el directorio; al desmarcar «Quiero figurar», deja de verse.",
        "Figurar es opcional: su perfil lo ven solo estudiantes y personal dentro del sistema, y su correo solo quien usted "
        "acepte ayudar."),
    "empleadores": Tratamiento(
        "Empleadores",
        "Organización, sector y nombres, correo y cargo de la persona de contacto.",
        "Invitar a los empleadores a las encuestas de seguimiento de egresados.",
        "La Dirección de Carrera, la Coordinación académica, Gestión de datos y la Comisión de calidad.",
        "Mientras el empleador esté activo; se puede desactivar.",
        "Los datos del contacto se usan solo para invitarle a las encuestas de empleadores; regístrelos con su acuerdo."),
    "perfil": Tratamiento(
        "Perfil de docentes e investigadores",
        "Nombres, grados, categoría, producción, proyectos, identificadores (ORCID y otros) y fecha de nacimiento.",
        "La gestión académica y científica de la Carrera y su difusión.",
        "El personal de la Carrera, dentro del sistema. Fuera de él, solo si usted activa «Perfil público»: nombre, grados, "
        "producción y proyectos (también en los datos abiertos). La fecha de nacimiento la ven solo usted y la "
        "Administración del sistema; los informes usan tramos de edad.",
        "Mientras la persona tenga relación con la Carrera, y después como registro histórico de su producción.",
        "Su perfil lo ve el personal de la Carrera y, si usted lo publica, cualquier persona; la fecha de nacimiento solo "
        "la ven usted y la Administración del sistema."),
}

# Formularios que piden datos personales: (módulo de rutas, clave de TRATAMIENTOS). La prueba exige que el módulo llame a
# `aviso_privacidad("<clave>")`.
FORMULARIOS = (
    ("app.estudiantil.rutas.estudiante", "estudiantes"),        # consentimiento del estudiante
    ("app.estudiantil.rutas.responder", "encuestas"),           # /encuesta/<enlace>
    ("app.estudiantil.rutas.evaluacion", "evaluacion_docente"),
    ("app.estudiantil.rutas.orientacion", "buzon"),
    ("app.servicios.rutas.auxiliaturas", "auxiliaturas"),       # postulación
    ("app.servicios.rutas.oportunidades", "oportunidades"),     # postulación
    ("app.egresados.rutas.directorio", "directorio"),           # perfil de egresado
    ("app.egresados.rutas.empleadores", "empleadores"),
    ("app.investigacion.rutas.perfil", "perfil"),
)

CONTACTO = ("Para ver, corregir o pedir que se eliminen sus datos, diríjase a la Dirección de Carrera. Las dudas sobre el "
            "sistema las atiende la Administración del sistema.")
