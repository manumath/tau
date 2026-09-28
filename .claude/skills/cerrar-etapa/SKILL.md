---
name: cerrar-etapa
description: Checklist para terminar una etapa o cambio en TAU antes de responder al usuario - lint, estilos, pruebas (con navegador), revisión visual, documentación (guía, PLAN.md, README, mantenimiento) y commit. Úsala al terminar cualquier cambio de código, o cuando el usuario diga «commitea» o «sigue».
---

# Cerrar una etapa

El usuario pide un commit por etapa. Antes de hacerlo:

## 1. Código

```bash
uvx pyflakes app scripts tests 2>&1 | grep -v "redefinition of unused"   # las rutas repiten get/post: normal
```
Sin variables sin usar, imports que sobran ni nombres indefinidos.

## 2. Estilos

Si se usó una clase de Tailwind que antes no existía: `scripts/estilos.sh` y confirme
`static/css/tailwind.css` en el commit. `tests/test_estilos.py` avisa si falta.

## 3. Pruebas

```bash
uv run pytest -q                 # rápido (~1,5 min)
uv run pytest -q --navegador     # antes del commit: flujos en Chrome, errores de JS y CSP
```
Si una prueba falla porque la regla cambió a propósito, actualice la expectativa **y** diga en la
respuesta qué regla cambió. Nunca borre una prueba para que pase. Agregue pruebas para lo nuevo
(lógica, permisos por rol y la pantalla).

## 4. Datos

- ¿Hubo migración? Skill `nueva-migracion` (probada sobre copias, no sobre `data/portal.db`).
- ¿Cambian los datos de ejemplo? `PORTAL_DB=<scratch>/s.db uv run python scripts/seed.py` en una base nueva.

## 5. Revisión visual

Si cambió algo que se ve: skill `captura-visual` y revise los PNG.

## 6. Documentación (en el mismo commit)

- `docs/guia-de-uso.md`: cómo lo usa cada rol (usted, sin jerga).
- `PLAN.md`: decisiones del instituto con fecha, qué se hizo (migraciones, acciones, módulos) y lo
  que queda por confirmar, en la sección de la fase o una nueva.
- `README.md`: solo si cambian la estructura, la configuración (`PORTAL_*`) o las convenciones.
- `docs/mantenimiento.md`: número de la última migración y procedimientos.
- `CLAUDE.md`: si cambió una regla que cualquier agente debe saber.

## 7. Commit

- En `main` (así trabaja este proyecto), mensaje en español: título «Fase N, paso X: …» o una
  frase clara; cuerpo con qué y por qué. Termine con la línea `Co-Authored-By` que indique el
  sistema.
- `git add` de rutas concretas (`app scripts tests docs PLAN.md migrations static/css/tailwind.css …`),
  nunca `data/`, `.herramientas/` ni PDFs de IAC-CINDA.

## 8. Respuesta al usuario

En español (tú): qué cambió en sus términos, decisiones que tomó el agente y deben confirmarse,
efectos en su base de desarrollo (migraciones que su servidor aplicará) y lo pendiente.
