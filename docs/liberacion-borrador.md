# Liberación de TAU: contexto y decisiones provisionales (borrador, 15-nov-2026)

Borrador de trabajo, **no es una decisión del instituto** ni está en `PLAN.md`. Resume el análisis de factibilidad del
plan de liberación (AGPLv3, versión útil para otras unidades de la UMSA). Para que se vuelva decisión, la Dirección debe
confirmarlo y pasar a `PLAN.md` con fecha.

> **Nota:** las secciones 4 y 6 (módulos y panel) quedaron reemplazadas por
> [modularizacion-plan.md](modularizacion-plan.md), que achica el núcleo, mantiene auxiliaturas en la versión libre y
> detalla la arquitectura.

## 1. Estado real del repositorio frente al plan pegado

- Ya existe: configuración por entorno (`app/comun/config.py`, unas 43 variables `TAU_*`), datos de demostración
  (`scripts/seed.py`, personajes ficticios, correos `@instituto.test`), marca centralizada (`app/comun/marca.py`,
  `layout.isotipo()`/`layout.logotipo()`) y `.gitignore` con `data/`, `*.db`, `.env*`, `/iac-cinda/`, `/politicas/`.
- Falta: `LICENSE`, `NOTICE`, `CITATION.cff`, `.env.example`, logotipo y paleta genéricos, y `instance_umsa/`.
- El repositorio **ya es público**: la política «zero-leak» aplica desde ahora y no basta con revisar los archivos
  rastreados.

## 2. Puntos bloqueantes

1. **Historial de git.** `datos/iac-cinda/Guia-de-Antecedentes-pregrado-2025.xlsx` está en los commits `7e9c314`,
   `e9a45b2` y `0c8392a`. No se ha abierto para ver si contiene personas reales. Si las contiene, purgar el historial
   (`git filter-repo`) choca con la regla de no reescribirlo: decide el usuario.
2. **`catalogos/MSC2020.tsv`.** La licencia de la clasificación MSC (se entiende que CC BY-NC-SA) sería incompatible con
   AGPL. **No verificado**: confirmar en la fuente y, si se confirma, sacarlo del repositorio.
3. `pyproject.toml` rastrea el nombre y el correo personal del autor: confirmar si deben quedar en el paquete público.

## 3. Alcance del desacoplamiento

- Unas 83 menciones de UMSA, FCPN, IIMAT o Carrera de Matemática en `app/`, 127 en `tests/` (8 archivos con literales) y
  varias migraciones sembradas (`0013`, `0022`, `0023`, `0032`) que no se pueden editar una vez aplicadas.
- **No parametrizar** categorías docentes (están en CHECKs de SQL), roles ni permisos (`REGLAS_ADMIN`, `ACCIONES`):
  documentarlos como configuración de referencia. **Sí parametrizar**: nombres, marca, periodos, topes de carga
  horaria, marco de calidad (CSV) y módulos activos.
- Mantener una sola fuente de configuración (variables `TAU_*` y `.env.example`); un `config.yaml` sumaría PyYAML y una
  segunda fuente de verdad.
- NOTICE debe citar más terceros que FastHTML y HTMX: MonsterUI, Franken UI, KaTeX, Tailwind (MIT), Montserrat y EB
  Garamond (OFL), lxml, Pillow, apsw, entre otros. Las citas legales del plan (Ley 1322, D.S. 24582, D.S. 3251, plazo
  de 90 días, formulario PI 147) **no están verificadas**: las revisa Asesoría Jurídica de la UMSA antes de firmar.

## 4. Módulos propuestos para la versión libre

- **Núcleo (siempre activo):** `comun` (cuentas, roles, auditoría, vínculos, unidades, correo), `investigacion`
  (perfiles, productos, proyectos, informes, CV), carga horaria y asignación docente, avisos, búsqueda y página pública.
- **Opcionales:** planes de estudio, gestiones y oferta; calidad (SIAC) con el marco como datos cargables; estudiantes,
  egresados y encuestas; comunicados y eventos.
- **Complemento de la instancia UMSA-CMAT (fuera de la versión libre):** auxiliaturas (reglamento HCU 424/2023
  incrustado), proyectos de grado y tribunales, tutoría y apoyo estudiantil, IA con su gobernanza, e importaciones de
  calidad con la agencia.
- Criterio: entra al núcleo lo que no depende de reglas de una unidad ni de datos sensibles de estudiantes; es opcional
  lo que depende de un marco normativo cargable como dato; sale lo que lleva el reglamento de la Carrera en el código.

## 5. Dependencias medidas (imports de Python entre paquetes)

| Paquete | Depende de |
|---|---|
| `comun` | nada |
| `investigacion` | comun 143; ia 6; calidad 3; academico 1; estudiantil 1 |
| `academico` | comun 90; servicios 7; estudiantil 3; calidad 2 |
| `egresados` | comun 17; estudiantil 2 |
| `estudiantil` | comun 67; academico 7; servicios 4; investigacion 3; ia 2 |
| `servicios` | comun 48; investigacion 11; estudiantil 7; academico 1; egresados 1 |
| `ia` | comun 11; investigacion 6; calidad 4 |
| `calidad` | comun 109; investigacion 13; academico 8; estudiantil 4; ia 4; egresados 2 |

- Es un monolito modular: el núcleo está limpio. Los nudos son `mis_pendientes` (junta academico, calidad y
  estudiantil), la búsqueda global, la navegación, y la pareja `estudiantil`–`servicios`.
- No se midió el acoplamiento por SQL; hay claves foráneas de `calidad` hacia `proyecto`, `producto` y `asignatura`.
- Las migraciones no se modularizan: un módulo apagado conserva sus tablas vacías. El interruptor oculta rutas y menú,
  no el esquema, y apagar nunca borra datos.

## 6. Panel de módulos (propuesta)

- Tabla `modulo_activo` (una migración), registro de módulos en código con nombre, descripción y dependencias, y valor
  inicial desde una variable de entorno.
- Un único filtro para el menú (`app/navegacion.py`) y para la autorización de rutas (404 en el servidor, también en
  `/publico/*`, `/api/v1/*`, parciales HTMX y tareas programadas). Ocultar el menú no basta.
- Pantalla solo de Administración del sistema, con auditoría. Estimación: 2 a 4 días más pruebas (módulo apagado
  devuelve 404, dependencias respetadas, CI con solo el núcleo).
- `PLAN §72` congela módulos hasta concluir el piloto: decidir con la Dirección si esto va antes o después.

## 7. Orden sugerido

1. Abrir el xlsx del historial, confirmar la licencia del MSC y decidir sobre el historial.
2. `.env.example`, `.gitignore` ampliado e `instance_umsa/` como mecanismo de carga de marca, datos y textos.
3. Marca genérica τ y paleta neutra, con pruebas parametrizadas.
4. Registro de módulos, filtro de rutas y panel; separar `mis_pendientes`, búsqueda y navegación.
5. Literales de `app/` y `tests/` a `config`; decidir sobre los datos sembrados por migraciones.
6. `LICENSE`, `NOTICE`, `README.md` y `CITATION.cff`; borradores de `docs_tramite_umsa/` con revisión jurídica.
