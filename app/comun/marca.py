"""Identidad visual del sistema (PLAN §55 y §74): los colores de la interfaz, de los gráficos y de las exportaciones.

Aquí está la marca **genérica** (el isotipo τ de `static/img/marca/` y una paleta azul petróleo). La unidad que instala
el sistema pone la suya en la carpeta `marca/` de su instancia: `marca.toml` con los colores y, con los mismos nombres
de archivo, sus imágenes (`app/comun/componentes/recursos.py` las sirve en lugar de las genéricas). De aquí salen el tema
de la interfaz (`css_del_tema`, que la aplicación sirve en `/tema.css`), los gráficos de los informes y la prueba de
contraste (`tests/test_marca.py`), que revisa la paleta genérica y la de cada instancia del repositorio.

`PRINCIPAL` es el color de la interfaz; `ACENTO`, el de los detalles decorativos y el membrete; los errores y los botones
que destruyen algo usan `destructive`, nunca el acento (si los botones fueran del color de la marca, «Guardar» y
«Eliminar» se confundirían).
"""
import re
import tomllib
from functools import cache

from app.comun import config

PRINCIPAL = "#1d4059"
ACENTO = "#c2630f"
SECUNDARIO = "#0f7a8c"
NEUTRO = "#64707a"

# Panel de la marca (PLAN §63): el menú lateral y el lienzo de las páginas de ingreso llevan un fondo del color
# principal que baja hacia el secundario, con la marca en blanco. `acento` es el color de la marca en detalles que no
# son texto ni errores (la cinta de los títulos, la marca del enlace activo); en oscuro se aclara, como `destructive`.
PANEL = {
    "claro": {"lateral": "205 51% 23%", "lateral-fin": "190 60% 20%", "lateral-foreground": "0 0% 100%",
              "acento": "28 86% 41%"},
    "oscuro": {"lateral": "205 45% 13%", "lateral-fin": "190 55% 12%", "lateral-foreground": "210 20% 96%",
               "acento": "32 90% 62%"},
}
# Opacidad del texto del menú sobre el panel: enlaces y títulos de grupo (clases text-lateral-foreground/NN).
OPACIDAD_MENU = (0.85, 0.7)

# Variables del tema de Franken UI (HSL sin «hsl()», como las suyas). En modo oscuro el color principal no se lee sobre
# el fondo: se usa un tono aclarado del mismo matiz y el fondo es una versión muy oscura.
TEMA = {
    "claro": {
        "background": "0 0% 100%", "foreground": "205 30% 12%",
        "card": "0 0% 100%", "card-foreground": "205 30% 12%",
        "popover": "0 0% 100%", "popover-foreground": "205 30% 12%",
        "muted": "205 20% 96%", "muted-foreground": "0 0% 38%",
        "border": "205 18% 88%", "input": "205 18% 88%",
        "primary": "205 51% 23%", "primary-foreground": "0 0% 100%",
        "secondary": "205 20% 95%", "secondary-foreground": "205 51% 23%",
        "accent": "205 20% 95%", "accent-foreground": "205 51% 23%",
        "destructive": "0 72% 41%", "destructive-foreground": "0 0% 100%",
        "ring": "190 90% 28%",
        **PANEL["claro"],
    },
    "oscuro": {
        "background": "205 40% 8%", "foreground": "210 20% 96%",
        "card": "205 40% 8%", "card-foreground": "210 20% 96%",
        "popover": "205 40% 8%", "popover-foreground": "210 20% 96%",
        "muted": "205 28% 16%", "muted-foreground": "210 12% 68%",
        "border": "205 24% 21%", "input": "205 24% 21%",
        "primary": "203 60% 74%", "primary-foreground": "205 45% 13%",
        "secondary": "205 28% 16%", "secondary-foreground": "210 20% 96%",
        "accent": "205 28% 16%", "accent-foreground": "210 20% 96%",
        "destructive": "0 80% 68%", "destructive-foreground": "205 40% 8%",
        "ring": "188 70% 50%",
        **PANEL["oscuro"],
    },
}
# Series de los gráficos (van sobre la hoja blanca de los informes): los colores de la marca y un quinto, claro.
GRAFICOS = (PRINCIPAL, SECUNDARIO, ACENTO, NEUTRO, "#6fb3c2")
CLASE_TEMA = "uk-theme-tau"   # la pone static/js/tema-inicial.js en <html>


def leer(carpeta) -> dict:
    """La marca de una instancia (`marca/marca.toml`) como {principal, acento, secundario, neutro, graficos, tema, panel};
    {} si no la trae. El tema que devuelve ya incluye el panel, como `TEMA`."""
    archivo = carpeta / "marca" / "marca.toml"
    if not archivo.exists():
        return {}
    d = tomllib.loads(archivo.read_text(encoding="utf-8"))
    panel = d.get("panel", {})
    return {**d, "tema": {modo: {**d.get("tema", {}).get(modo, {}), **panel.get(modo, {})} for modo in ("claro", "oscuro")}}


_propia = leer(config.INSTANCIA)
if _propia:   # la marca de la unidad reemplaza a la genérica, valor por valor
    PRINCIPAL, ACENTO = _propia.get("principal", PRINCIPAL), _propia.get("acento", ACENTO)
    SECUNDARIO, NEUTRO = _propia.get("secundario", SECUNDARIO), _propia.get("neutro", NEUTRO)
    GRAFICOS = tuple(_propia.get("graficos") or (PRINCIPAL, SECUNDARIO, ACENTO, NEUTRO, GRAFICOS[4]))
    PANEL = {modo: {**PANEL[modo], **_propia.get("panel", {}).get(modo, {})} for modo in PANEL}
    TEMA = {modo: {**TEMA[modo], **_propia["tema"][modo]} for modo in TEMA}
# Nombres anteriores, de cuando la marca era solo la de la Carrera de Matemática.
AZUL, ROJO, TURQUESA, GRIS = PRINCIPAL, ACENTO, SECUNDARIO, NEUTRO


def hex_de(hsl: str) -> str:
    """'224 36% 24%' → '#273353'."""
    h, s, luz = (float(x.rstrip("%")) for x in hsl.split())
    s, luz = s / 100, luz / 100
    c = (1 - abs(2 * luz - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = luz - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return "#" + "".join(f"{round((v + m) * 255):02x}" for v in (r, g, b))


def mezcla(color: str, fondo: str, opacidad: float) -> str:
    """Color '#rrggbb' que resulta de pintar `color` con esa opacidad sobre `fondo`."""
    canales = [round(int(color[i:i + 2], 16) * opacidad + int(fondo[i:i + 2], 16) * (1 - opacidad)) for i in (1, 3, 5)]
    return "#" + "".join(f"{c:02x}" for c in canales)


def contraste(color_a: str, color_b: str) -> float:
    """Razón de contraste WCAG entre dos colores '#rrggbb'."""
    def luminancia(color):
        canales = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    claro, oscuro = sorted((luminancia(color_a), luminancia(color_b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


# --- Tema de la interfaz ---------------------------------------------------------------------------------------------

_IMAGENES = ("--uk-form-checkbox-image", "--uk-form-checkbox-image-indeterminate", "--uk-form-radio-image",
             "--uk-form-list-image", "--uk-divider-icon-image", "--uk-list-bullet-image")


def _imagenes(css: str, selector: str, colores: dict[str, str]) -> list[str]:
    bloque = re.search(re.escape(selector) + r"\{([^}]*)\}", css).group(1)
    salida = []
    for nombre in _IMAGENES:
        valor = re.search(re.escape(nombre) + r":\s*(.*?)(?=;--|$)", bloque, re.S).group(1)
        for antes, despues in colores.items():
            valor = valor.replace(antes, despues)
        salida.append(f"  {nombre}: {valor};")
    return salida


def generar_css(tema: dict) -> str:
    """El tema de Franken UI con esos colores. Franken UI define cada tema con variables HSL y con imágenes SVG en línea
    (casillas, radios, viñetas) que llevan sus colores escritos: se toman las del tema azul y se cambian por los de la
    marca, en el mismo papel."""
    css = (config.RAIZ / "static/vendor/franken-ui/core.min.css").read_text()
    c, o = tema["claro"], tema["oscuro"]
    h = lambda v: "%23" + hex_de(v)[1:]  # noqa: E731  (color dentro de un data: URL)
    claro = {"%232563eb": h(c["primary"]), "%23f8fafc": h(c["primary-foreground"]),
             "%2364748b": h(c["muted-foreground"]), "%23e2e8f0": h(c["border"]), "%23020817": h(c["foreground"])}
    oscuro = {"%233b82f6": h(o["primary"]), "%230f172a": h(o["primary-foreground"]),
              "%2394a3b8": h(o["muted-foreground"]), "%231e293b": h(o["border"]), "%23f8fafc": h(o["foreground"])}
    lineas = ["/* Tema de la interfaz: lo genera app/comun/marca.py con la marca de esta instalación. */",
              f".{CLASE_TEMA} {{", *[f"  --{k}: {v};" for k, v in c.items()],
              *_imagenes(css, ".uk-theme-blue", claro), "}",
              f".dark.{CLASE_TEMA} {{", *[f"  --{k}: {v};" for k, v in o.items()],
              *_imagenes(css, ".dark.uk-theme-blue", oscuro), "}",
              "/* La hoja imprimible es papel blanco: dentro de ella rigen los colores claros también en modo oscuro. */",
              f".{CLASE_TEMA} .hoja {{", *[f"  --{k}: {v};" for k, v in c.items()], "}", ""]
    return "\n".join(lineas)


@cache
def css_del_tema() -> str:
    """La hoja de estilos del tema de esta instalación (`/tema.css`)."""
    return generar_css(TEMA)
