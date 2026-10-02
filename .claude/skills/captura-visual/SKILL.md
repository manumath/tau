---
name: captura-visual
description: Revisar visualmente pantallas de TAU con capturas de Playwright sobre una base temporal (seed o copia de data/portal.db), con la cuenta y los roles que haga falta. Úsala después de cambiar una pantalla, un formulario, una tabla o estilos, antes de dar por terminada una etapa.
---

# Captura visual

Levanta TAU con uvicorn en un puerto libre sobre una **base temporal** (nunca `data/portal.db`,
que usa el servidor de desarrollo del usuario), ingresa con una cuenta, recorre rutas (con clics
opcionales) y guarda PNG. Falla si la página registra errores de JavaScript.

## Uso

```bash
uv run python .claude/skills/captura-visual/capturar.py [opciones] RUTA [RUTA ...]
```

- `RUTA` puede llevar textos en los que hacer clic antes de capturar, separados por `|`:
  `"/docencia/carga|Noether, Emmy"`.
- `--base seed` (por omisión) crea una base con `scripts/seed.py`; `--base dev` copia
  `data/portal.db` con `.backup` (datos reales del usuario: solo para mirar, no para publicar).
  `--base RUTA` copia una base preparada (p. ej., un seed temporal al que se le agregó un caso que
  el seed no trae, como una propuesta en borrador); la original no se toca.
- `--como EMAIL --clave CLAVE`: por omisión la cuenta admin de ejemplo del README.
- Cuentas de ejemplo con contraseña temporal (Emmy, Alan, Sofía…): agregue `--clave-prueba` con
  una clave inventada; se fija **solo en la copia**.
- `--rol ROL:SIGLA` (repetible) asigna roles en la copia, p. ej. `--rol direccion_carrera:CMAT`
  (la cuenta admin no la tiene y es la única que define vínculos y carga).
- `--salida DIR` (use el scratchpad de la sesión), `--movil` (375 × 812), `--pagina-completa`, `--oscuro` (revisar el modo oscuro).
- `--pdf`: guarda el PDF como lo imprime Chrome (A4, membrete, pie con «Página X de Y») en vez de
  PNG; para revisar los informes impresos. Para mirarlo, convierta páginas a PNG
  (`sips -s format png archivo.pdf --out pagina.png` da la primera en macOS).

Ejemplos:

```bash
# Ventana de vínculo de la Dirección de Carrera
uv run python .claude/skills/captura-visual/capturar.py --rol direccion_carrera:CMAT \
  --salida "$SCRATCH" "/admin/usuarios|Vínculo"
# Vista de una investigadora en móvil
uv run python .claude/skills/captura-visual/capturar.py --como emmy.noether@instituto.test \
  --clave Captura-prueba-2026 --clave-prueba --movil --salida "$SCRATCH" /proyectos
```

## Después

1. Abra cada PNG con la herramienta Read y revíselo: textos cortados, columnas que se parten
   (fechas: `whitespace-nowrap`), íconos sueltos en su propia línea (`flex items-start gap-1`),
   contraste, estados vacíos.
2. Si usó una clase de Tailwind nueva y se ve sin estilo: `scripts/estilos.sh` (ver skill
   `cerrar-etapa`).
3. Muestre al usuario solo las capturas que aporten (SendUserFile), no todas.

## Reglas

- Nunca escriba contraseñas reales ni use cuentas reales: solo las de ejemplo del seed o las de
  prueba fijadas en la copia.
- No use el puerto 5001 ni `data/portal.db` directamente: son del servidor del usuario.
