"""Catálogo de funciones de IA (PLAN §59). Cada función declara su módulo, el nivel máximo de datos que recibe, si
seudonimiza, si puede ir a un proveedor externo, quién puede pedirla y quién aprueba su resultado. En la base solo
se guarda si está activa y quién responde por ella (`ia_funcion`); todas nacen apagadas.

Las funciones se registran en `app/ia/catalogo.py`.
"""
from dataclasses import dataclass, field
from typing import Callable

from app.ia.clasificacion import PERSONAL

# Módulos donde la IA no puede invocarse (principio 2). Solo se amplía.
VEDADOS = {
    "auxiliaturas": "calificación y fases de auxiliaturas",
    "docencia_asignacion": "asignación docente y carga horaria",
    "desempeno": "evaluación del desempeño",
    "tutoria": "tutoría (notas y reuniones)",
    "grado_tribunal": "resoluciones y calificaciones de tribunales de grado",
    "personas": "decisiones sobre una persona identificada",
}


def _propio(auth: dict, uso: dict) -> bool:
    return uso["usuario_id"] == auth["id"]


@dataclass(frozen=True)
class Funcion:
    clave: str
    nombre: str
    modulo: str
    descripcion: str
    nivel_max: int                      # nivel de datos máximo que acepta (0 a 2; el 3 nunca)
    revisor: str                        # quién revisa, para la marca: «revisado por la Dirección del Instituto»
    puede_pedir: Callable[[dict, str | None], bool]          # (auth, entidad) → ¿puede pedir un borrador?
    puede_aprobar: Callable[[dict, dict], bool] = field(default=_propio)   # (auth, uso)
    al_aprobar: Callable[[dict, str], None] | None = None     # efecto del texto aprobado (uso, texto); None: solo se muestra
    seudonimizar: bool = False          # reemplaza nombres de personas por [PERSONA_n] antes de enviar
    externa: bool = True                # False: solo el modelo local, aunque el nivel lo permita
    max_tokens: int = 1500
    datos: str = ""                     # qué datos usa, en palabras (página «Uso de IA en TAU»)
    # Funciones de elección (clasificar, sugerir evidencias): el borrador es una lista de valores separados por comas y
    # `opciones(uso)` → [(valor, etiqueta, enlace o None)] para que la persona marque los que acepta.
    opciones: Callable[[dict], list[tuple[str, str, str | None]]] | None = None


FUNCIONES: dict[str, Funcion] = {}


def registrar(f: Funcion) -> Funcion:
    if f.modulo in VEDADOS:
        raise ValueError(f"La IA no puede usarse en {VEDADOS[f.modulo]}.")
    if not 0 <= f.nivel_max <= PERSONAL:
        raise ValueError("Una función de IA recibe a lo más datos de nivel 2 (personal).")
    FUNCIONES[f.clave] = f
    return f


def obtener(clave: str) -> Funcion | None:
    return FUNCIONES.get(clave)
