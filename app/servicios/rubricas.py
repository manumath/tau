"""Rúbricas de las auxiliaturas según el Reglamento Específico de Auxiliares Académicos del Pregrado (Res. HCU 424/2023; PLAN §70, etapa 4).

- **Méritos (30 puntos):** formularios 2-1 (docencia), 2-2 (investigación y Beca Tesis) y 2-3 (interacción social). Seis secciones con su
  tope; cada línea da puntos por unidad (curso, año, semestre, participación) y la sección 4 convierte la nota de la materia a puntos.
- **Examen oral (35 puntos):** formulario 4, cinco criterios.

Todo es cálculo puro: no toca la base de datos. Una línea es (clave, texto, puntos por unidad, unidad); la clave es la del formulario
(«1a», «2b»…) y es la que se guarda en `calificacion_detalle`."""

MERITOS_MAXIMO = 30
ORAL_MAXIMO = 35
LIMITE_CANTIDAD = 99       # tope razonable por línea, para que un error de tipeo no desborde nada

# Nota obtenida en la materia que postula → puntos (sección 4, la misma en los tres formularios).
ESCALA_MATERIA = ((51, 59, 2), (60, 69, 4), (70, 79, 6), (80, 89, 8), (90, 100, 10))
SECCION_MATERIA = "4"

_CURSO = "curso"
_ANIO, _SEM = "año", "semestre"
_VEZ = "vez"

_COMUN = {
    "experiencia": ("Experiencia académica", [("a", "Auxiliar de docencia, investigación o interacción social (por año)", 1, _ANIO),
                                                ("b", "Auxiliar de docencia, investigación o interacción social (por semestre)", 0.5, _SEM)]),
    "vida": ("Participación en la vida universitaria", [("a", "Representante ante el HCU, el CAU o el CAF", 1, _VEZ),
                                                          ("b", "Representante ante el HCF o el HCC", 1, _VEZ)]),
    "tribunal": ("Delegado del tribunal estudiantil", [("a", "Examen de competencia para docentes", 1, _VEZ),
                                                        ("b", "Examen de competencia para auxiliares de docencia, investigación o interacción social",
                                                         1, _VEZ)]),
}


def _seccion(numero: str, titulo: str, maximo: int, lineas: list[tuple[str, str, float, str]]) -> dict:
    return {"numero": numero, "titulo": titulo, "maximo": maximo,
            "lineas": [(f"{numero}{letra}", texto, puntos, unidad) for letra, texto, puntos, unidad in lineas]}


def _comunes(numero: str, clave: str, maximo: int) -> dict:
    titulo, lineas = _COMUN[clave]
    return _seccion(numero, titulo, maximo, lineas)


FORMULARIOS = {
    "2-1": {
        "titulo": "Acta de calificación de méritos para auxiliares de docencia",
        "secciones": [
            _seccion("1", "Formación pedagógica (curso oficial de capacitación en psicopedagogía, mínimo 60 horas)", 5,
                     [("a", "Curso aprobado", 3, _CURSO), ("b", "Asistencia a cursos", 1, _CURSO)]),
            _seccion("2", "Cursos de capacitación relacionados con su carrera", 5,
                     [("a", "Asistencia a cursos y seminarios", 1, _CURSO),
                      ("b", "Expositor u organizador en cursos, conferencias, seminarios u otros", 2, _CURSO)]),
            _comunes("3", "experiencia", 5),
            _seccion(SECCION_MATERIA, "Calificación obtenida en la materia que postula", 10, []),
            _comunes("5", "vida", 2),
            _comunes("6", "tribunal", 3),
        ],
    },
    "2-2": {
        "titulo": "Acta de calificación de méritos para auxiliares de investigación",
        "secciones": [
            _seccion("1", "Formación pedagógica (curso oficial de capacitación en psicopedagogía, mínimo 60 horas)", 3,
                     [("a", "Curso aprobado", 2, _CURSO), ("b", "Asistencia a cursos", 1, _CURSO)]),
            _seccion("2", "Cursos de capacitación relacionados con su carrera", 9,
                     [("a", "Participación y disertación oral en congresos científicos", 3, _CURSO),
                      ("b", "Participación y disertación con póster en congresos", 2, _CURSO),
                      ("c", "Artículos de investigación publicados", 4, _CURSO),
                      ("d", "Miembro del comité editorial de una revista científica", 2, _CURSO),
                      ("e", "Presentación de artículos de investigación inéditos", 2, _CURSO),
                      ("f", "Participación en proyectos de investigación", 2, _CURSO),
                      ("g", "Asistencia a congresos científicos", 1, _CURSO)]),
            _comunes("3", "experiencia", 3),
            _seccion(SECCION_MATERIA, "Calificación obtenida en la materia que postula", 10, []),
            _comunes("5", "vida", 2),
            _comunes("6", "tribunal", 3),
        ],
    },
    "2-3": {
        "titulo": "Acta de calificación de méritos para auxiliares de interacción social",
        "secciones": [
            _seccion("1", "Formación pedagógica (curso oficial de capacitación en psicopedagogía, mínimo 60 horas)", 5,
                     [("a", "Curso aprobado", 3, _CURSO), ("b", "Asistencia a cursos", 2, _CURSO)]),
            _seccion("2", "Participación, congresos y ferias", 7,
                     [("a", "Participación y disertación en cursos, congresos y otros", 3, _CURSO),
                      ("b", "Participación y difusión con póster en congresos y otros", 3, _CURSO),
                      ("c", "Participación en ferias de interacción social", 2, _CURSO),
                      ("d", "Asistencia a cursos, talleres, congresos y otros", 1, _CURSO)]),
            _comunes("3", "experiencia", 3),
            _seccion(SECCION_MATERIA, "Calificación obtenida en la materia que postula", 10, []),
            _comunes("5", "vida", 2),
            _comunes("6", "tribunal", 3),
        ],
    },
}
_POR_MODALIDAD = {"docencia": "2-1", "investigacion": "2-2", "beca_tesis": "2-2", "interaccion_social": "2-3"}

# Examen oral (formulario 4): criterio → (texto, máximo). Suman 35.
ORAL = (("conocimiento", "Conocimiento del tema", 7), ("preparacion", "Preparación del tema", 8), ("didactica", "Didáctica", 10),
        ("metodologia", "Metodología", 5), ("respuestas", "Respuestas a las preguntas realizadas", 5))
ORAL_TIEMPOS = "20 minutos de exposición y 10 de preguntas"


def formulario_de(modalidad: str) -> str:
    return _POR_MODALIDAD[modalidad]


def secciones(modalidad: str) -> list[dict]:
    return FORMULARIOS[formulario_de(modalidad)]["secciones"]


def claves_meritos(modalidad: str) -> list[str]:
    """Todas las entradas del formulario: las líneas de cada sección y la nota de la materia (clave '4')."""
    return [clave for s in secciones(modalidad) for clave in ([s["numero"]] if s["numero"] == SECCION_MATERIA else
                                                              [linea[0] for linea in s["lineas"]])]


def puntos_materia(nota: float) -> int:
    """Puntos de la sección 4 según la nota de la materia que postula (menos de 51: ninguno)."""
    for desde, hasta, puntos in ESCALA_MATERIA:
        if desde <= nota < hasta + 1:
            return puntos
    return 0


def calcular_meritos(modalidad: str, entradas: dict[str, float]) -> dict:
    """Puntaje de méritos de un postulante: {'secciones': [{numero, titulo, maximo, puntos, sin_tope}], 'total'}. Cada sección se topa en su
    máximo; el total no pasa de 30. `entradas`: clave de línea → cantidad (en la sección 4, la nota de la materia, de 0 a 100)."""
    res, total = [], 0.0
    for s in secciones(modalidad):
        if s["numero"] == SECCION_MATERIA:
            bruto = float(puntos_materia(entradas.get(SECCION_MATERIA, 0)))
        else:
            bruto = sum(entradas.get(clave, 0) * puntos for clave, _t, puntos, _u in s["lineas"])
        puntos = min(bruto, s["maximo"])
        res.append({"numero": s["numero"], "titulo": s["titulo"], "maximo": s["maximo"], "puntos": puntos, "sin_tope": bruto})
        total += puntos
    return {"secciones": res, "total": min(total, MERITOS_MAXIMO)}


def validar_meritos(modalidad: str, crudo: dict) -> tuple[dict[str, float], list[str]]:
    """Convierte lo escrito en el formulario (texto por clave) en cantidades. Vacío es cero. → (cantidades, errores)."""
    cantidades, errores = {}, []
    for clave in claves_meritos(modalidad):
        texto = str(crudo.get(clave, "") or "").strip().replace(",", ".")
        if texto == "":
            cantidades[clave] = 0.0
            continue
        try:
            v = float(texto)
        except ValueError:
            errores.append(f"«{clave}»: escriba un número.")
            continue
        limite = 100 if clave == SECCION_MATERIA else LIMITE_CANTIDAD
        if not 0 <= v <= limite:
            errores.append(f"«{clave}»: debe estar entre 0 y {limite}.")
        cantidades[clave] = v
    return cantidades, errores


def calcular_oral(entradas: dict[str, float]) -> float:
    return min(sum(min(entradas.get(clave, 0), maximo) for clave, _t, maximo in ORAL), ORAL_MAXIMO)


def validar_oral(crudo: dict) -> tuple[dict[str, float], list[str]]:
    cantidades, errores = {}, []
    for clave, texto_criterio, maximo in ORAL:
        texto = str(crudo.get(clave, "") or "").strip().replace(",", ".")
        if texto == "":
            cantidades[clave] = 0.0
            continue
        try:
            v = float(texto)
        except ValueError:
            errores.append(f"{texto_criterio}: escriba un número.")
            continue
        if not 0 <= v <= maximo:
            errores.append(f"{texto_criterio}: va de 0 a {maximo}.")
        cantidades[clave] = v
    return cantidades, errores
