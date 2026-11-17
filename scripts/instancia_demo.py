"""Qué instancia usan los scripts que arman datos de demostración (seed, manual, medir, capturas; PLAN §74).

Esos datos de ejemplo (docentes, oferta de MAT-111, proyectos del instituto) son los de la Carrera de Matemática, que
viven en `instancias/cmat`, una carpeta que no se versiona en el repositorio público. Con `TAU_INSTANCIA` se elige otra;
sin ella se usa `instancias/cmat` y, si no está en este equipo, el script se detiene con un mensaje claro. Debe llamarse
**antes** de importar `app`, porque `app.comun.config` lee la variable al importarse.
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MENSAJE = ("Este script arma datos de demostración de la Carrera de Matemática (docentes, oferta de MAT-111…) y necesita\n"
           "instancias/cmat, que no está en el repositorio público. Con otra instancia, defina TAU_INSTANCIA; el manual y\n"
           "el seed de otra unidad necesitan sus propios datos de demostración (docs/manual-plan.md).")


def fijar() -> Path:
    """Deja `TAU_INSTANCIA` definida y devuelve su carpeta (se detiene si no hay ninguna que usar)."""
    if "TAU_INSTANCIA" not in os.environ:
        cmat = RAIZ / "instancias" / "cmat"
        if not cmat.is_dir():
            sys.exit(MENSAJE)
        os.environ["TAU_INSTANCIA"] = str(cmat)
    return Path(os.environ["TAU_INSTANCIA"])
