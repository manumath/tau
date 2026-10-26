"""Genera estilos/tema-cmat.css, el tema de Franken UI con los colores de la Carrera (app/comun/marca.py).

Uso: uv run python scripts/tema_marca.py && scripts/estilos.sh

Franken UI define cada tema con variables HSL y con imágenes SVG en línea (casillas, radios, viñetas) que
llevan sus colores escritos: se toman las del tema azul y se cambian sus colores por los de la marca.
tests/test_marca.py comprueba que el archivo está al día con marca.py.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.comun import marca  # noqa: E402

DESTINO = RAIZ / "estilos/tema-cmat.css"
IMAGENES = ("--uk-form-checkbox-image", "--uk-form-checkbox-image-indeterminate", "--uk-form-radio-image",
            "--uk-form-list-image", "--uk-divider-icon-image", "--uk-list-bullet-image")


def _imagenes(css: str, selector: str, colores: dict[str, str]) -> list[str]:
    bloque = re.search(re.escape(selector) + r"\{([^}]*)\}", css).group(1)
    salida = []
    for nombre in IMAGENES:
        valor = re.search(re.escape(nombre) + r":\s*(.*?)(?=;--|$)", bloque, re.S).group(1)
        for antes, despues in colores.items():
            valor = valor.replace(antes, despues)
        salida.append(f"  {nombre}: {valor};")
    return salida


def generar() -> str:
    css = (RAIZ / "static/vendor/franken-ui/core.min.css").read_text()
    c, o = marca.TEMA["claro"], marca.TEMA["oscuro"]
    h = lambda v: "%23" + marca.hex_de(v)[1:]  # noqa: E731  (color dentro de un data: URL)
    # Colores del tema azul de Franken UI → los del tema de la marca, en el mismo papel.
    claro = {"%232563eb": h(c["primary"]), "%23f8fafc": h(c["primary-foreground"]),
             "%2364748b": h(c["muted-foreground"]), "%23e2e8f0": h(c["border"]), "%23020817": h(c["foreground"])}
    oscuro = {"%233b82f6": h(o["primary"]), "%230f172a": h(o["primary-foreground"]),
              "%2394a3b8": h(o["muted-foreground"]), "%231e293b": h(o["border"]), "%23f8fafc": h(o["foreground"])}
    lineas = ["/* Generado por scripts/tema_marca.py desde app/comun/marca.py: no se edita a mano. */",
              ".uk-theme-cmat {", *[f"  --{k}: {v};" for k, v in c.items()],
              *_imagenes(css, ".uk-theme-blue", claro), "}",
              ".dark.uk-theme-cmat {", *[f"  --{k}: {v};" for k, v in o.items()],
              *_imagenes(css, ".dark.uk-theme-blue", oscuro), "}", ""]
    return "\n".join(lineas)


if __name__ == "__main__":
    DESTINO.write_text(generar())
    print(f"Escrito {DESTINO.relative_to(RAIZ)}")
