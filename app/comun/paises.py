"""Países: nombres normalizados (en español) para contar la internacionalización.

- `normalizar` convierte variantes («EE. UU.», «USA», «United States») al nombre canónico.
- `por_codigo` traduce el código ISO de dos letras que entrega OpenAlex.
- `desde_texto` deduce el país de una afiliación («…, Oxford, UK» → «Reino Unido»).
"""
import re

from app.comun.db import sin_tildes

# nombre canónico → (código ISO, variantes). Países con los que más colabora la matemática
# latinoamericana; los demás se guardan tal como se escriban.
PAISES = {
    "Alemania": ("DE", "germany", "deutschland"), "Argentina": ("AR",), "Australia": ("AU",),
    "Austria": ("AT", "osterreich"), "Bélgica": ("BE", "belgium", "belgique"), "Bolivia": ("BO",),
    "Brasil": ("BR", "brazil"), "Canadá": ("CA", "canada"), "Chile": ("CL",), "China": ("CN", "p. r. china", "pr china"),
    "Colombia": ("CO",), "Corea del Sur": ("KR", "korea", "south korea", "republic of korea", "corea"),
    "Costa Rica": ("CR",), "Cuba": ("CU",), "Dinamarca": ("DK", "denmark"), "Ecuador": ("EC",),
    "España": ("ES", "spain", "espana"), "Estados Unidos": ("US", "usa", "u.s.a.", "united states", "united states of america",
                                                            "ee. uu.", "ee.uu.", "eeuu", "estados unidos de america"),
    "Finlandia": ("FI", "finland"), "Francia": ("FR", "france"), "Grecia": ("GR", "greece"),
    "Hungría": ("HU", "hungary"), "India": ("IN",), "Irán": ("IR", "iran"), "Irlanda": ("IE", "ireland"),
    "Israel": ("IL",), "Italia": ("IT", "italy"), "Japón": ("JP", "japan"), "México": ("MX", "mexico"),
    "Noruega": ("NO", "norway"), "Países Bajos": ("NL", "netherlands", "the netherlands", "holanda", "holland"),
    "Paraguay": ("PY",), "Perú": ("PE", "peru"), "Polonia": ("PL", "poland"), "Portugal": ("PT",),
    "Reino Unido": ("GB", "uk", "u.k.", "united kingdom", "england", "scotland", "wales", "great britain"),
    "República Checa": ("CZ", "czech republic", "czechia"), "Rusia": ("RU", "russia", "russian federation"),
    "Suecia": ("SE", "sweden"), "Suiza": ("CH", "switzerland", "schweiz", "suisse"), "Turquía": ("TR", "turkey", "turkiye"),
    "Uruguay": ("UY",), "Venezuela": ("VE",),
}
_CODIGOS = {v[0]: k for k, v in PAISES.items()}
_ALIAS = {}
for _nombre, (_codigo, *_variantes) in PAISES.items():
    for _v in (_nombre, *_variantes):
        _ALIAS[sin_tildes(_v).lower()] = _nombre


def normalizar(texto: str | None) -> str | None:
    """Nombre canónico si se reconoce; si no, el texto limpio (o None si viene vacío)."""
    t = (texto or "").strip()
    if not t:
        return None
    return _ALIAS.get(sin_tildes(t).lower().rstrip("."), _ALIAS.get(sin_tildes(t).lower(), t))


def por_codigo(codigo: str | None) -> str | None:
    return _CODIGOS.get((codigo or "").upper())


def desde_texto(afiliacion: str | None) -> str | None:
    """País mencionado en una afiliación; primero en su último tramo («…, Oxford, UK»)."""
    if not afiliacion:
        return None
    tramos = [sin_tildes(x).lower().strip(" .") for x in re.split(r"[,;]", afiliacion) if x.strip()]
    for tramo in reversed(tramos):
        if tramo in _ALIAS:
            return _ALIAS[tramo]
    texto = " " + sin_tildes(afiliacion).lower() + " "
    for alias in sorted(_ALIAS, key=len, reverse=True):
        if len(alias) > 3 and re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", texto):
            return _ALIAS[alias]
    return None


def es_extranjero(pais: str | None, propio: str) -> bool | None:
    """True/False si se sabe; None si no hay país."""
    p = normalizar(pais)
    return None if not p else p != normalizar(propio)


def nombres() -> list[str]:
    return sorted(PAISES, key=sin_tildes)
