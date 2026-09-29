# CLAUDE.md — TAU

**TAU | Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática**
(CMAT) y su Instituto de Investigación Matemática (IIMAT), FCPN, UMSA, La Paz, Bolivia. Reúne la
actividad científica, la gestión académica (planes, oferta, docencia, carga horaria) y la evidencia
para la acreditación ante IAC-CINDA. Nació como «Portal de Investigación» del IIMAT: los nombres
técnicos (`PORTAL_*`, `portal.db`, servicio `portal`, app de Fly.io) conservan «portal» a propósito.

Léase con: [README.md](README.md) (estructura, configuración, convenciones HTMX y seguridad),
[PLAN.md](PLAN.md) (diseño, reglas de negocio y **todas las decisiones del instituto con fecha**;
§22–25 son la ampliación actual), [docs/guia-de-uso.md](docs/guia-de-uso.md),
[docs/mantenimiento.md](docs/mantenimiento.md).

## Idioma y tono

- Responda al usuario en **español, tuteando**. La interfaz y la guía tratan de **usted**.
- Código, comentarios, commits y documentación en español, con tildes y signos correctos.
- En la interfaz: «el sistema» (no «el portal») y el nombre desde `config.NOMBRE_SISTEMA`.

## Stack y comandos

FastHTML 0.14 + HTMX + MonsterUI (Franken UI) + Tailwind 3.4 compilado + SQLite (fastlite, apsw,
fastmigrate). Python con [uv](https://docs.astral.sh/uv/). **El stack se conserva** (decisión de
la fase 0): no proponga Django, PostgreSQL ni SPA salvo que el usuario lo pida.

```bash
uv run python main.py                 # servidor de desarrollo (puerto 5001, lo suele tener abierto el usuario)
uv run pytest -q                      # ~460 pruebas, cada una con base temporal
uv run pytest -q --navegador          # + flujos en Chrome (Playwright)
uvx pyflakes app scripts tests        # «redefinition of unused get/post» es normal en rutas
scripts/estilos.sh                    # recompilar Tailwind tras usar una clase nueva
PORTAL_DB=/ruta/tmp.db uv run python scripts/seed.py   # base de ejemplo aparte
```

## Estructura

- `app/comun`: base de datos y dialecto SQL (`db.py`), autenticación (`auth.py`, `REGLAS_ADMIN`),
  roles y permisos (`permisos.py`), personas, cuentas, **vínculos** (`vinculos.py`), unidades,
  correo, componentes de interfaz. **No importa de los otros paquetes.**
- `app/investigacion`: perfiles, productos, actividades, proyectos, propuestas institucionales,
  líneas, revistas, importaciones (DOI, arXiv, BibTeX, OpenAlex).
- `app/academico`: planes de estudio, gestiones, oferta y asignación docente, carga horaria.
- `app/acreditacion`: CV, memoria, anexo de I+D+i, estudiantes.
- Cada paquete: lógica en `<tema>.py`, pantallas en `rutas/<tema>.py` (`APIRouter`), registradas en
  `main.py`. `migrations/` (fastmigrate), `scripts/`, `tests/` (`tests/navegador/` con Playwright),
  `datos/planes/` (planes de estudio en CSV), `static/` (vendor con versión fija), `estilos/`.

## Reglas de negocio que no se deducen del código a simple vista

- **Dependencia única:** el vínculo de cada persona es con la Carrera (el IIMAT forma parte de
  ella). **Solo la Dirección de Carrera** define categoría y vínculo (altas, cambios, término,
  carga horaria contratada). La Dirección del Instituto gestiona el ciclo de vida de los proyectos
  institucionales. Administración del sistema: cuentas, roles (a pedido de las direcciones) y
  auditoría. El Comité de acreditación ve todo y no modifica.
- **Vínculo por periodos:** contratados, interinos e invitados con fecha de término obligatoria;
  titular permanente (se termina a mano con motivo: retiro, renuncia, despido, fallecimiento).
- **Carga horaria:** unidades de 32 h/mes; carga contratada 32–160 h/mes por periodo de vínculo,
  distribuida por actividad (docencia, investigación, extensión, gestión, otras) y que suma el
  total. Cada materia como titular = 32 h/mes; auxiliares y cursos de verano/invierno no suman.
  JCE = carga / 160. Participar en proyectos no exige carga.
- **Carga en proyectos** (solo institucionales): el responsable la asigna por participante; sale de
  la investigación o la extensión del vínculo vigente y rige solo mientras ese periodo está vigente.
  En un nuevo periodo no se reasigna sola; los responsables reciben avisos (`carga_proyectos`).
- **Gestiones:** I, INV (julio), II, VER (enero del año siguiente, contado con la gestión
  anterior: VER-2026 = enero de 2027). Verano e invierno solo los dictan titulares.
- **Proyectos:** individuales (los elimina su responsable) e institucionales de **investigación** o
  de **interacción social**; los proponen titulares y contratados en la convocatoria de septiembre;
  periodo octubre–septiembre. Líneas de investigación obligatorias solo en los de investigación.
- **Informes:** cuenta lo producido mientras la persona estaba vinculada, con la categoría de esa
  fecha. Las inconsistencias de datos oficiales (PDF de planes) se cargan tal cual y se marcan.
- **Cargo y unidad o grupo** del perfil se calculan (`app/comun/adscripcion.py`): «Docente
  Investigador» con carga de investigación, si no «Docente»; unidad = proyectos que dirige, en que
  participa, detalle de extensión y de gestión del vínculo, o «Carrera de Matemática».
- Fecha de nacimiento: la ve la administración y la propia persona; los informes usan tramos.

## Cuidados al trabajar aquí

- **`data/portal.db` es la base del servidor de desarrollo del usuario**, que aplica solas las
  migraciones al recargar. No la modifique ni pruebe contra ella: trabaje sobre copias
  (`sqlite3 data/portal.db ".backup 'copia.db'"`) y avise qué cambiará cuando su servidor migre.
- No use el puerto 5001 (servidor del usuario): la skill `captura-visual` usa uno libre.
- Contraseñas: solo las de ejemplo del seed o de prueba fijadas en copias temporales. Nunca pida
  ni use contraseñas del sistema operativo o cuentas reales.
- Descargas e instalaciones (paquetes, binarios, plugins): pida permiso explícito antes.
- No versione `data/`, `.herramientas/`, ni los PDF de IAC-CINDA.
- Nunca edite una migración aplicada; nunca borre una prueba para que pase.
- Seguridad: autorización en el servidor en cada ruta; CSRF por `Origin`; CSP propia
  (`app/comun/cabeceras.py`), sin recursos de otros sitios.

## Forma de trabajo

- El usuario decide por etapas («Sí, sigue», «commitea»): **un commit por etapa**, en `main`, con
  mensaje en español y la línea `Co-Authored-By` que indique el sistema.
- Cuando una regla del instituto no está clara, pregunte con opciones concretas; las decisiones
  van a PLAN.md con fecha. Si tomó una decisión por su cuenta, dígalo al final para que la confirme.
- Documente en el mismo commit: guía (usuarios), PLAN.md (decisiones y estado), README o
  mantenimiento si corresponde, y este archivo si cambia algo que todo agente debe saber.

## Skills del proyecto (`.claude/skills/`)

| Skill | Cuándo |
|---|---|
| `cerrar-etapa` | Al terminar cualquier cambio: lint, estilos, pruebas con navegador, revisión visual, documentación y commit. |
| `nueva-migracion` | Al cambiar el esquema o mover datos: numeración, SQL de SQLite, pruebas sobre copias, seed y docs. |
| `nueva-ruta-o-permiso` | Al crear pantallas, rutas HTMX o acciones con roles: dónde va, `ACCIONES`, `REGLAS_ADMIN`, pruebas por rol, textos. |
| `captura-visual` | Para revisar pantallas: `capturar.py` levanta TAU sobre una base temporal y guarda PNG con la cuenta y roles pedidos. |

## Plugins recomendados (catálogo oficial `claude-plugins-official`; no instalados)

Instalarlos es decisión del usuario (`/plugin install NOMBRE@claude-plugins-official` en una
terminal interactiva de Claude Code):

- `pyright-lsp`: diagnósticos y navegación de Python mientras se edita (requiere `pyright`).
- `claude-md-management`: auditar y mantener este CLAUDE.md con lo aprendido en cada sesión.
- `security-guidance`: avisos de seguridad al editar (útil con datos personales y permisos).
- `code-simplifier`: limpiar código tras cambios grandes, sin cambiar el comportamiento.
- `commit-commands`: flujo de commits (este proyecto ya tiene su propio checklist en `cerrar-etapa`).
- `skill-creator`: para crear o mejorar skills como las de `.claude/skills/`.
