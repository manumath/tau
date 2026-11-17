"""Lo propio de la unidad que instala el sistema, leído de `instancia.toml` (PLAN §74): textos y parámetros que no son
datos de la base ni secretos del despliegue. La carpeta es `config.INSTANCIA` (`TAU_INSTANCIA`, o la de ejemplo)."""
import tomllib
from functools import cache

from app.comun import config


@cache
def _datos() -> dict:
    archivo = config.INSTANCIA / "instancia.toml"
    return tomllib.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}


def valor(clave: str, por_defecto=None):
    """Un dato de `instancia.toml`; `por_defecto` si la instancia no lo trae."""
    return _datos().get(clave, por_defecto)
