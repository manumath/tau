"""Ajustes del texto que devuelve el modelo antes de mostrarlo (PLAN §59).

- `cifras`: ninguna cifra del borrador proviene del modelo. Las instrucciones le piden marcadores (`{{productos}}`) que
  se reemplazan por los valores de la base; cualquier otro número que el modelo escriba y que no esté en los datos que
  recibió (un año del periodo, un número del título de un artículo) se reemplaza por «[cifra por verificar]».
- `sin_citas`: quita las frases copiadas al pie de la letra de las respuestas abiertas (8 palabras seguidas o más), para
  que una síntesis no reproduzca lo que escribió una persona.
"""
import re

POR_VERIFICAR = "[cifra por verificar]"
CITA_OMITIDA = "[cita omitida]"
_NUMERO = re.compile(r"(?<![\w\[{])\d+(?:[.,]\d+)*(?![\w\]}])")


def numeros(texto: str) -> set[str]:
    return set(_NUMERO.findall(texto or ""))


def cifras(texto: str, valores: dict[str, int | float | str], permitidos: set[str] = frozenset()) -> str:
    """Reemplaza {{clave}} por su valor y marca las cifras que el modelo escribió por su cuenta."""
    def marcador(m):
        return str(valores[m.group(1)]) if m.group(1) in valores else POR_VERIFICAR
    # Primero los números sueltos (antes de insertar los valores, que no se marcan).
    texto = _NUMERO.sub(lambda m: m.group(0) if m.group(0) in permitidos else POR_VERIFICAR, texto)
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", marcador, texto)


def _palabras(texto: str) -> list[str]:
    return re.findall(r"\w+", texto.lower())


def sin_citas(texto: str, respuestas: list[str], n: int = 8) -> str:
    """Reemplaza cada tramo de `n` o más palabras copiado de alguna respuesta."""
    tramos = set()
    for r in respuestas:
        w = _palabras(r)
        tramos |= {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
    if not tramos:
        return texto
    tokens = list(re.finditer(r"\w+", texto))
    marcar = [False] * len(tokens)
    bajos = [t.group(0).lower() for t in tokens]
    for i in range(len(tokens) - n + 1):
        if tuple(bajos[i:i + n]) in tramos:
            for j in range(i, i + n):
                marcar[j] = True
    if not any(marcar):
        return texto
    partes, ultimo, i = [], 0, 0
    while i < len(tokens):
        if marcar[i]:
            j = i
            while j + 1 < len(tokens) and marcar[j + 1]:
                j += 1
            partes += [texto[ultimo:tokens[i].start()], CITA_OMITIDA]
            ultimo = tokens[j].end()
            i = j + 1
        else:
            i += 1
    return "".join(partes) + texto[ultimo:]
