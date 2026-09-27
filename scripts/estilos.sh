#!/bin/sh
# Compila los estilos de Tailwind a static/css/tailwind.css.
#
# Hay que ejecutarlo cuando se usa en el código una clase de Tailwind que antes no se usaba
# (la prueba tests/test_estilos.py lo detecta). Requiere la herramienta oficial de Tailwind v3.4.17
# en .herramientas/tailwindcss (no se versiona). Para obtenerla (macOS con Apple Silicon; en
# Linux, tailwindcss-linux-x64):
#
#   mkdir -p .herramientas
#   curl -L -o .herramientas/tailwindcss \
#     https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-macos-arm64
#   chmod +x .herramientas/tailwindcss
#
# y compare su SHA-256 con sha256sums.txt de la misma versión.
set -e
cd "$(dirname "$0")/.."
MONSTERUI_DIR=$(.venv/bin/python -c "import monsterui, os; print(os.path.dirname(monsterui.__file__))")
export MONSTERUI_DIR
.herramientas/tailwindcss -c estilos/tailwind.config.js -i estilos/entrada.css -o static/css/tailwind.css --minify
