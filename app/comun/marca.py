"""Identidad visual de la Carrera de Matemática (Manual de Identidad Institucional; PLAN.md §55).

Un solo lugar para los colores de la marca: de aquí salen el tema de la interfaz (estilos/tema-cmat.css, que
genera scripts/tema_marca.py), los gráficos de los informes y la prueba de contraste (tests/test_marca.py).

Colores del manual (web): azul marino Pantone 2767C y rojo 485C, principales; turquesa 7713C y gris 424C,
secundarios. En la interfaz el azul marino es el color principal; el rojo queda para la marca, los acentos
del membrete y las acciones que destruyen algo (si los botones fueran rojos, «Guardar» y «Eliminar» se
confundirían).
"""
AZUL = "#273353"
ROJO = "#be141b"
TURQUESA = "#007c8f"
GRIS = "#6c6c6c"

# Variables del tema de Franken UI (HSL sin «hsl()», como las suyas). En modo oscuro el azul marino no se
# lee sobre el fondo: el color principal es un tono aclarado del mismo matiz y el fondo, un azul muy oscuro.
TEMA = {
    "claro": {
        "background": "0 0% 100%", "foreground": "224 30% 12%",
        "card": "0 0% 100%", "card-foreground": "224 30% 12%",
        "popover": "0 0% 100%", "popover-foreground": "224 30% 12%",
        "muted": "224 20% 96%", "muted-foreground": "0 0% 38%",
        "border": "224 18% 88%", "input": "224 18% 88%",
        "primary": "224 36% 24%", "primary-foreground": "0 0% 100%",
        "secondary": "224 20% 95%", "secondary-foreground": "224 36% 24%",
        "accent": "224 20% 95%", "accent-foreground": "224 36% 24%",
        "destructive": "358 81% 41%", "destructive-foreground": "0 0% 100%",
        "ring": "188 100% 28%",
    },
    "oscuro": {
        "background": "224 36% 9%", "foreground": "220 20% 96%",
        "card": "224 36% 9%", "card-foreground": "220 20% 96%",
        "popover": "224 36% 9%", "popover-foreground": "220 20% 96%",
        "muted": "224 25% 17%", "muted-foreground": "220 12% 68%",
        "border": "224 22% 22%", "input": "224 22% 22%",
        "primary": "222 55% 76%", "primary-foreground": "224 36% 14%",
        "secondary": "224 25% 17%", "secondary-foreground": "220 20% 96%",
        "accent": "224 25% 17%", "accent-foreground": "220 20% 96%",
        "destructive": "358 80% 66%", "destructive-foreground": "224 36% 9%",
        "ring": "186 70% 50%",
    },
}

# Series de los gráficos (van sobre la hoja blanca de los informes): los colores de la marca y, para la
# quinta, un turquesa claro.
GRAFICOS = (AZUL, TURQUESA, ROJO, GRIS, "#66b0bc")


def hex_de(hsl: str) -> str:
    """'224 36% 24%' → '#273353'."""
    h, s, luz = (float(x.rstrip("%")) for x in hsl.split())
    s, luz = s / 100, luz / 100
    c = (1 - abs(2 * luz - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = luz - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return "#" + "".join(f"{round((v + m) * 255):02x}" for v in (r, g, b))


def contraste(color_a: str, color_b: str) -> float:
    """Razón de contraste WCAG entre dos colores '#rrggbb'."""
    def luminancia(color):
        canales = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    claro, oscuro = sorted((luminancia(color_a), luminancia(color_b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)
