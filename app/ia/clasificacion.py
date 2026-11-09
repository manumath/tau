"""Clasificación de los datos que pueden alimentar a la IA (PLAN §59, principio 3).

Cada dato que se entrega al servicio de IA lleva su origen («tabla.columna», o un nombre lógico como
«persona.nombre»). El servicio rechaza un origen sin clasificar: así, una columna nueva no llega al modelo
sin que alguien decida su nivel.

| Nivel | Qué | Proveedor permitido |
|---|---|---|
| 0 · Público | títulos de productos, líneas, indicadores publicados | local o externo (con retención cero) |
| 1 · Interno | descripciones de proyectos y actividades, textos del marco de calidad | local o externo (con retención cero) |
| 2 · Personal | nombres, CV, respuestas abiertas nominales | local; externo solo seudonimizado |
| 3 · Sensible | fecha de nacimiento, tutoría, respuestas anónimas individuales, contacto | ninguno |
"""
PUBLICO, INTERNO, PERSONAL, SENSIBLE = 0, 1, 2, 3
NIVELES = {PUBLICO: "Público", INTERNO: "Interno", PERSONAL: "Personal", SENSIBLE: "Sensible"}

# Orígenes que son nombres de personas: la seudonimización los reemplaza por [PERSONA_n].
NOMBRES = {"persona.nombre"}

CAMPOS: dict[str, int] = {
    # 0 · Público
    "producto.titulo": PUBLICO,
    "producto.resumen": PUBLICO,
    "producto.anio": PUBLICO,
    "producto.revista": PUBLICO,
    "producto.tipo": PUBLICO,
    "linea_investigacion.nombre": PUBLICO,
    "area_investigacion.nombre": PUBLICO,
    "msc.texto": PUBLICO,
    "indicador.publicado": PUBLICO,
    "periodo.texto": PUBLICO,
    "marcadores.texto": PUBLICO,            # lista de marcadores de cifras ({{productos}}), sin sus valores
    # 1 · Interno
    "proyecto.nombre": INTERNO,
    "proyecto.descripcion": INTERNO,
    "proyecto.objetivos": INTERNO,
    "actividad.titulo": INTERNO,
    "actividad.descripcion": INTERNO,
    "criterio_calidad.texto": INTERNO,
    "indicador.valor": INTERNO,
    "evidencia_calidad.titulo": INTERNO,
    "juicio_criterio.fortalezas": INTERNO,
    "juicio_criterio.debilidades": INTERNO,
    "pregunta.texto": INTERNO,
    # 2 · Personal
    "persona.nombre": PERSONAL,
    "investigador.bio": PERSONAL,
    "respuesta.texto_nominal": PERSONAL,
    # Respuestas abiertas de una pregunta, juntas, mezcladas y sin metadatos (también las de encuestas anónimas: así
    # agregadas no identifican a nadie; una respuesta anónima suelta sigue siendo sensible). Solo modelo local.
    "encuesta.respuestas_agregadas": PERSONAL,
}

# 3 · Sensible: nunca se envían, ni siquiera se aceptan en la entrada. Basta el prefijo de la tabla con «*».
SENSIBLES = {
    "datos_personales.*",        # fecha de nacimiento
    "tutoria_asignacion.*", "tutoria_reunion.*",
    "respuesta.texto_anonimo", "respuesta_item.*",
    "usuario.email", "persona_externa.email", "contacto.*",
}


def nivel(origen: str) -> int:
    """Nivel del origen; ValueError si no está clasificado."""
    tabla = origen.split(".", 1)[0]
    if origen in SENSIBLES or f"{tabla}.*" in SENSIBLES:
        return SENSIBLE
    if origen not in CAMPOS:
        raise ValueError(f"Dato sin clasificar para la IA: {origen}")
    return CAMPOS[origen]
