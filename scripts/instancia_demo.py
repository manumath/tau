"""Qué instancia usan los scripts que arman datos de demostración (seed, manual, medir, capturas; PLAN §74).

Los datos de ejemplo (docentes, oferta, proyectos del instituto) se cargan sobre la instancia que se elija. Con
`TAU_INSTANCIA` se indica cuál; sin ella se usa `instancias/cmat` si está en este equipo (no se versiona) y, si no,
`instancias/ejemplo`, la ficticia del repositorio. Con la de ejemplo, el manual sale neutro (`manual.neutralizar`): sin
nombres ni siglas de la Carrera de Matemática. Debe llamarse **antes** de importar `app`, porque `app.comun.config` lee
la variable al importarse.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
def fijar() -> Path:
    """Deja `TAU_INSTANCIA` definida y devuelve su carpeta (`cmat` si existe; si no, `ejemplo`)."""
    if "TAU_INSTANCIA" not in os.environ:
        cmat = RAIZ / "instancias" / "cmat"
        os.environ["TAU_INSTANCIA"] = str(cmat if cmat.is_dir() else RAIZ / "instancias" / "ejemplo")
    return Path(os.environ["TAU_INSTANCIA"])
