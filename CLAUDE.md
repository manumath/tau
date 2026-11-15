# CLAUDE.md — TAU

**TAU | Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática**
(CMAT) y su Instituto de Investigación Matemática (IIMAT), FCPN, UMSA, La Paz, Bolivia. Reúne la
actividad científica, la gestión académica (planes, oferta, docencia, carga horaria) y el Sistema Interno
de Aseguramiento de la Calidad (SIAC) de la Carrera. Nació como «Portal de Investigación» del IIMAT: los nombres
técnicos (`PORTAL_*`, `portal.db`, servicio `portal`, app de Fly.io) conservan «portal» a propósito.

Léase con: [README.md](README.md) (estructura, configuración, convenciones HTMX y seguridad),
[PLAN.md](PLAN.md) (diseño, reglas de negocio y **todas las decisiones del instituto con fecha**;
§22–25 son la ampliación actual), [docs/guia-de-uso.md](docs/guia-de-uso.md),
[docs/mantenimiento.md](docs/mantenimiento.md), [docs/piloto.md](docs/piloto.md) y [docs/gobernanza.md](docs/gobernanza.md).

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
uv run pytest -q                      # ~675 pruebas, cada una con base temporal
uv run pytest -q --navegador          # + flujos en Chrome (Playwright)
uvx ruff check app scripts tests main.py   # reglas en pyproject.toml; debe quedar sin avisos
scripts/estilos.sh                    # recompilar Tailwind tras usar una clase nueva
PORTAL_DB=/ruta/tmp.db uv run python scripts/seed.py   # base de ejemplo aparte
uv run python scripts/medir.py [--inflar] [--escrituras]   # rendimiento y escrituras en las lecturas (unos minutos)
```

GitHub Actions (`.github/workflows/pruebas.yml`) corre ruff y `pytest --navegador` en cada push a `main`: una prueba
que solo pasa en este equipo (logos originales, `.herramientas/`, `data/`) falla allí. Las versiones de uv y ruff y
las acciones (por hash) están fijadas ahí; al cambiarlas, ver `docs/mantenimiento.md` §5.2.

## Estructura

- `app/comun`: base de datos y dialecto SQL (`db.py`), autenticación (`auth.py`, `REGLAS_ADMIN`),
  roles y permisos (`permisos.py`), personas, cuentas, **vínculos** (`vinculos.py`), unidades,
  correo, componentes de interfaz. **No importa de los otros paquetes.**
- `app/investigacion`: perfiles, productos, actividades, proyectos, propuestas institucionales,
  líneas, revistas, importaciones (DOI, arXiv, BibTeX, OpenAlex).
- `app/academico`: planes de estudio (con su ciclo de vida: `reformas`, `malla`, `menciones`, `equivalencias`, `vigencia`;
  PLAN §65), gestiones (con su ciclo de vida: `semestre`, `cambios`; PLAN §66), oferta y asignación docente, carga horaria.
- `app/calidad`: Aseguramiento de la Calidad (PLAN §57): memoria, informe de I+D+i, cuerpo académico, calidad de
  datos, seguimiento estudiantil. Sin nombres de agencias ni de sus instrumentos (decisión del 6-nov-2026).
- `app/estudiantil`: seguimiento estudiantil (PLAN §49): cohortes, carga del CSV de Seguimiento Académico,
  actividad estudiantil y encuestas. Sin materias ni notas. `app/egresados`: titulación, seguimiento,
  indicadores de egresados (PLAN §50) y registro de empleadores (PLAN §57).
- `app/ia`: IA con criterio humano (PLAN §59). Todo uso de un modelo pasa por `servicio.generar`. Cada dato se
  clasifica en `clasificacion.py`; los módulos vedados (auxiliaturas, grado, oferta, carga y tutoría) no importan
  `app.ia`. Las salidas nacen como borrador y solo surten efecto con `servicio.texto_aprobado`. Las pruebas reemplazan
  `servicio._enviar`: nunca salen a la red. Las decisiones de diseño van en `docs/ia/decisiones.md`. Las funciones y
  el contexto que recibe cada una se arman solo en `catalogo.py`; las pantallas usan `rutas/panel.bloque` y muestran el
  texto aprobado con `panel.texto_aprobado` (lleva la marca). Ninguna cifra sale del modelo (`textos.cifras`).
- `app/servicios`: comunicados y eventos, auxiliaturas y proyectos de grado (PLAN §58), con pantallas del personal en
  `/servicios/*` y de los estudiantes en `/estudiante/{comunicados,auxiliaturas,tribunal,grado}`.
- Cada paquete: lógica en `<tema>.py`, pantallas en `rutas/<tema>.py` (`APIRouter`), registradas en
  `main.py`. El menú lateral se arma en `app/navegacion.py`: una pantalla nueva se agrega ahí, con el mismo
  permiso que su ruta. `migrations/` (fastmigrate), `scripts/`, `tests/` (`tests/navegador/` con Playwright),
  `datos/planes/` (planes de estudio en CSV), `datos/calidad/` (borrador del marco de calidad), `static/` (vendor con versión fija), `estilos/`.

## Reglas de negocio que no se deducen del código a simple vista

- **Dependencia única:** el vínculo de cada persona es con la Carrera (el IIMAT forma parte de
  ella). **Solo la Dirección de Carrera** define categoría y vínculo (altas, cambios, término,
  carga horaria contratada). La Dirección del Instituto gestiona el ciclo de vida de los proyectos
  institucionales. Administración del sistema: cuentas, roles (a pedido de las direcciones) y
  auditoría. La Comisión de calidad ve todo y solo registra evidencias y juicios de la autoevaluación (PLAN §57).
- **Vínculo por periodos:** contratados, interinos e invitados con fecha de término obligatoria;
  titular permanente (se termina a mano con motivo: retiro, renuncia, despido, fallecimiento).
- **Plan de mejora (PLAN §72):** acciones con actividades (`app/calidad/actividades_mejora.py`). El avance y el semáforo se
  calculan, no se guardan. Aprobado el plan (`marco_calidad.plan_aprobado_en`), el plazo de una actividad cambia solo por
  reprogramación (`reprogramacion_mejora`: el responsable pide y la Dirección de Carrera aprueba); nunca lo edite directo.
  El responsable de una actividad adjunta su evidencia en el mismo avance (`registrar_evidencia`, que la liga con
  `evidencia_calidad.actividad_id`), ve solo esas y no el repositorio: elija las evidencias de un avance con `actividades_mejora.evidencias_elegibles`, nunca con
  `evidencias.listar` (PLAN §72, etapa 11).
  Un **corte** (`cortes_mejora.py`) congela el estado de cada actividad: sus cifras no se recalculan después; solo los
  comentarios de un corte abierto cambian. El plan de la Carrera se carga de `datos/calidad/plan-de-mejora-2026-2030.csv`
  (`importar_mejora.py`), sin nombres de agencias ni columna de criterio de agencia. Las hojas imprimibles (`.hoja`) usan
  los colores claros también en modo oscuro: dentro de una, use la clase `apagado` para el texto secundario.
- **Planes de estudio (PLAN §65):** un plan está *en elaboración*, *vigente*, *en proceso de cierre* o *cerrado*, y los
  planes se agrupan en una **reforma curricular** (la que se revisa cada 10 años; puede traer 1, 2 o 3 programas). Programa =
  titulación (títulos distintos); mención = énfasis dentro de un mismo título. Un programa tiene a lo sumo un plan vigente.
  Un borrador solo lo ven quienes tienen `elaborar_planes` (Dirección de Carrera y Coordinación académica) y no entra en
  oferta, búsqueda, indicadores ni cohortes: toda consulta nueva sobre planes debe excluirlo (`estado <> 'elaboracion'`) y, si
  es para asignar estudiantes u ofertar, usar solo `vigente` y `cierre`. Poner en vigencia y cerrar es solo de la Dirección de
  Carrera (`decidir_planes`). `vigente_hasta` es el año del último ingreso. El catálogo `asignatura` es común a todos los
  planes: la misma sigla en dos planes es la misma asignatura (y equivalente por sí sola).
- **Servicios del estudiante (PLAN §67), con sus reglas de privacidad:** las marcas de «Mi plan de estudios» (`estudiante_aprobada`) son
  privadas (solo el estudiante y, si lo decide, su tutor; nunca informes ni Dirección). Las **señales** de apoyo se calculan al momento,
  no se guardan y solo las ve el estudiante; el personal ve solo los **casos** (`caso_apoyo`), que vencen a los seis meses si no se
  renuevan. Un envío **anónimo** del buzón no guarda `externo_id`, solo el día, no se audita y su ruta (`registros.RUTAS_ANONIMAS`) no
  lleva el usuario en el registro: no la ligue con la cuenta en ninguna consulta nueva. El retorno de una encuesta nunca muestra
  respuestas abiertas y, si es anónima, exige `MIN_ANONIMO`. Toda ruta nueva de `/estudiante/*` saca la ficha de la cuenta
  (`_requiere`) y no de la dirección; el menú del estudiante se arma en `navegacion.menu` (grupos «Mi carrera» y «Servicios») y la barra del
  teléfono usa `PRIORIDAD_MOVIL_ESTUDIANTE`. Las constancias las emite Kardex: TAU no las genera.
- **Servicios del docente (PLAN §68):** «Mis pendientes», el calendario, las preferencias de oferta y los programas son solo de la persona
  (siempre `auth["id"]`, nunca un id de la dirección). La **lista de curso** la ven solo los docentes del paralelo, con auditoría, ni siquiera la
  Dirección, y es una copia temporal que se borra al concluir la gestión (o una consulta a la API de Kardex que no guarda nada). La
  **evaluación docente** es anónima: no enlace la participación con la respuesta ni guarde hora, no muestre resultados con menos de
  `MIN_RESPUESTAS` ni un desglose que permita restarlos, y registre en `evaluacion_consulta` toda consulta ajena.
- **Servicios del investigador (PLAN §69):** «Mis pendientes», el calendario, el acceso abierto y las colaboraciones son solo de la persona
  (siempre `auth["id"]`, y 403 si la cuenta no es de investigador). El **acceso abierto** (`producto_acceso`) es una declaración propia
  que TAU no verifica ni exige: el perfil público y `/api/v1/*` muestran solo el enlace de lo declarado `abierto` o `depositado`, nunca el
  embargo, las notas ni los datos, y ningún indicador o informe lo usa sin una decisión nueva (PLAN §69). Las **colaboraciones** se derivan
  de `producto_autor` y `proyecto_participante` sin guardar nada y muestran solo nombre, institución y país: cada quien ve únicamente las
  suyas, nunca correo, ORCID ni documento.
- **Auxiliaturas (PLAN §58 y §70):** rige el **Reglamento Específico de Auxiliares Académicos del Pregrado** (Res. HCU 424/2023, mod. 364/2025); el
  de 2021 (251/2021) quedó sin efecto. Cada convocatoria guarda su `reglamento` y conserva sus reglas (`auxiliaturas.REGLAS`: mínimos, plazos): nunca
  recalcule una convocatoria con las reglas de otro. Solo se convoca sobre los semestres I y II, nunca INV ni VER. Los PDF del reglamento no se
  versionan; el resumen artículo por artículo está en PLAN §70. Con el reglamento de 2023: los méritos y el oral se califican por formulario
  (`rubricas.py` → `calificar_detalle`; cada miembro califica por su cuenta y la nota es el promedio), la comisión debe cumplir `revisar_comision`
  (art. 15), las invitaciones (`designaciones.py`) solo proceden tras una **segunda** convocatoria y TAU no guarda notas de Kardex (los mejores
  estudiantes los certifica Kardex y aquí solo se anota a quién se invitó). Los plazos de los arts. 12, 13, 14, 18, 20, 22, 23 y 27 solo advierten.
  Los formularios impresos están en `rutas/formularios.py`. El seguimiento posterior a la designación (asistencia, remoción) es del §71.
- **Gestiones (PLAN §66):** cada gestión (I, II, INV, VER) está *en planificación* (oferta y docentes se editan libremente y se
  puede borrar), *activa* (todo cambio pide fecha de efecto y motivo, queda en `gestion_cambio` y se avisa al docente; no se
  borra nada: `oferta.retirada_en`, `oferta_docente.desde/hasta`) o *concluida* (historial de solo lectura; solo la Dirección de
  Carrera la reabre). Activar, concluir y reabrir son de `decidir_gestion`. Toda edición de oferta o docentes debe comprobar
  `gestiones.edicion_libre(g)` o pasar por `app.academico.cambios`; toda consulta de lo vigente excluye lo retirado
  (`retirada_en IS NULL`, `hasta IS NULL`) y la carga cuenta por meses dictados (`oferta.tramos_de`).
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
- **Cuentas de estudiante (PLAN §49):** sin contraseña, ingresan por enlace al correo (`/acceso`) y solo llegan a
  `/estudiante`, `/avisos`, `/logout` y `/piloto` (comentarios del piloto) (`auth.RUTAS_ESTUDIANTE`): una ruta nueva del personal queda cerrada para ellos
  sin tocar nada, pero toda ruta nueva de `/estudiante` debe sacar la ficha de `estudiantes.cuenta_de(auth["id"])`, nunca de
  un id en la dirección. Si la dirección lleva el id de un trámite, una postulación o un ítem (PLAN §58), compruebe que es de
  esa ficha o que el estudiante integra ese tribunal. Se unen a la ficha por `cuenta_estudiante`, no por `persona_externa.usuario_id`.
- **Encuestas (PLAN §49 y §50):** las anónimas no enlazan la respuesta con la invitación ni guardan la hora, y no
  muestran resultados con menos de 5 respuestas (`encuestas.MIN_ANONIMO`), tampoco por pregunta (una opcional respondida
  por pocos sale `oculta` en `resultados`): cualquier vista o exportación nueva debe respetarlo. El enlace de `/encuesta/<enlace>` es público y personal; se borra al responder o cerrar.
- **Tutoría (PLAN §49):** las notas de las reuniones son confidenciales: las ve el tutor autor y la Dirección de Carrera
  (con auditoría); nunca van a informes, exportaciones ni a la pantalla de la Comisión de calidad. **Directorio de egresados (PLAN §50):** opcional y
  solo dentro del sistema; el correo de un estudiante y el de un egresado solo se comparten cuando el egresado acepta una solicitud.
- **Egresados (PLAN §50):** egresado = estudiante con estado «titulado» y fecha de titulación (se deduce). El seguimiento
  (encuestas con `encuesta.hito`) invita solo al último hito cumplido; los indicadores se calculan por `pregunta.clave` y
  muestran siempre el n. No cambie las opciones de las preguntas con clave en la plantilla de egresados.
- **Estudiantes (PLAN §49):** TAU no guarda materias ni notas (son de Seguimiento Académico); la clave de
  unión es el registro universitario (RU). De los estudiantes solo se guarda la edad al ingresar (no la
  fecha de nacimiento ni el CI). El tablero de cohortes es agregado; la situación académica individual la
  ve solo quien tiene `ver_seguimiento_estudiantil`.

## Cuidados al trabajar aquí

- **Módulos congelados (PLAN §72, 14-nov-2026):** hasta concluir el piloto con usuarios reales no se agrega ningún módulo;
  se consolida lo que existe (plan de mejora, rendimiento, brechas del plan de mejora, privacidad). Una pantalla nueva
  solo entra si la pide un usuario del piloto y tiene un responsable de sus datos. Si el usuario pide un módulo nuevo,
  recuérdeselo antes de planificarlo.
- **Privacidad (PLAN §72, etapa 8):** un formulario nuevo que pida datos personales lleva `layout.aviso_privacidad(clave)` sobre
  el botón de enviar y su módulo va en `privacidad.FORMULARIOS`. Si cambia quién ve un dato o cuánto se conserva, cambie el
  texto en `app/comun/privacidad.py` en el mismo commit: de ahí salen el aviso y la página `/publico/privacidad`.
- **Ningún GET escribe** (salvo el registro que la regla pide) y las listas largas van de 50 en 50 (`registros.cargar_mas`);
  `scripts/medir.py --escrituras` y `--inflar` lo revisan (`docs/mantenimiento.md` §5.11).

- **`data/portal.db` es la base del servidor de desarrollo del usuario**, que aplica solas las
  migraciones al recargar. No la modifique ni pruebe contra ella: trabaje sobre copias
  (`sqlite3 data/portal.db ".backup 'copia.db'"`) y avise qué cambiará cuando su servidor migre. Como recarga al guardar,
  una migración se escribe y se prueba **fuera** de `migrations/` y se copia allí solo cuando corre limpia (skill
  `nueva-migracion`).
- No use el puerto 5001 (servidor del usuario): la skill `captura-visual` usa uno libre.
- Contraseñas: solo las de ejemplo del seed o de prueba fijadas en copias temporales. Nunca pida
  ni use contraseñas del sistema operativo o cuentas reales.
- Descargas e instalaciones (paquetes, binarios, plugins): pida permiso explícito antes.
- No versione `data/`, `.herramientas/`, ni los PDF de agencias (`/iac-cinda/`) ni las políticas de la UMSA (`/politicas/`, PLAN §57). Las
  correspondencias con instrumentos de una agencia son privadas (PLAN §57). Tampoco los logos originales
  (`static/img/membrete/logo_*`, solo en local).
- **El repositorio es público** (<https://github.com/manumath/tau>): nada de datos reales, bases, correos ni contraseñas
  reales en commits, pruebas, seed ni documentación. Los commits usan el correo `noreply` de GitHub del autor
  (`git config user.email`); no lo cambie. No reescriba el historial ni haga `push --force` sin que el usuario lo pida.
- **Marca de la Carrera (PLAN §55):** los colores salen de `app/comun/marca.py` (tras cambiarlo:
  `uv run python scripts/tema_marca.py && scripts/estilos.sh`); errores y botones de quitar con `text-destructive`,
  nunca `text-red-*`; logos con `layout.isotipo()`/`layout.logotipo()` (versión blanca en oscuro). Los originales de la
  marca y sus fuentes comerciales (Gotham, Helvetica Neue, Garamond Pro) no se versionan: se usan Montserrat y EB Garamond.
  Sobre el panel azul marino (menú lateral, lienzo de las páginas sin sesión; PLAN §63) la marca va en blanco
  (`isotipo(blanco=True)`) y el texto con `text-lateral-foreground`; una página sin sesión pone su contenido en una
  tarjeta (`Card`), nunca suelto sobre el lienzo. El rojo decorativo es `acento`, no `destructive`.
- **Accesibilidad (PLAN §62):** etiquete los campos con `layout.campo("Texto", control)`, no con `FormLabel` suelto; el
  texto de color usa tono 700 u 800 con su variante `dark:` (los 500 y 600 no llegan a 4,5:1 sobre blanco).
  `tests/navegador/test_accesibilidad_pantallas.py` lo vigila (también un solo `<h1>` y ninguna fecha ISO a la vista):
  agregue allí las pantallas nuevas. Fechas y cifras en pantalla con `app/comun/formato.py` (`fecha`, `fecha_hora` para
  marcas UTC, `momento` para fecha y hora locales de un formulario, `periodo`, `numero`); ISO solo en exportaciones y formularios.
- Plantillas XLSX ajenas (formularios de agencias): nunca con openpyxl al guardar, que borra gráficos e
  imágenes; use `app/comun/xlsx_plantilla.py`, que escribe solo las celdas pedidas.
- Nunca edite una migración aplicada; nunca borre una prueba para que pase.
- Seguridad: autorización en el servidor en cada ruta (`tests/test_rutas_declaradas.py` falla con una ruta sin control
  reconocible; las que son para todo el personal van a su lista con el motivo); CSRF por `Origin`; CSP propia y estricta
  (`app/comun/cabeceras.py`), sin recursos de otros sitios ni JavaScript en el HTML: nada de
  `onclick`/`hx_on`/scripts en línea; use `data-accion` y compañía (`static/js/acciones.js`).

## Forma de trabajo

- El usuario decide por etapas («Sí, sigue», «commitea»): **un commit por etapa**, en `main`, con
  mensaje en español y la línea `Co-Authored-By` que indique el sistema.
- Cuando una regla del instituto no está clara, pregunte con opciones concretas; las decisiones
  van a PLAN.md con fecha. Si tomó una decisión por su cuenta, dígalo al final para que la confirme.
- Principios: la solución más simple que resuelva la causa de fondo, no un parche; toque solo lo
  necesario. Antes de presentar un cambio grande, pregúntese si hay una forma más limpia.
- No declare algo terminado sin evidencia (pruebas, captura o archivo generado; skill
  `cerrar-etapa`). Si algo se desvía a mitad de camino, deténgase y replantee en vez de insistir.
- Errores de código: corríjalos sin pedir ayuda. Reglas del instituto, datos reales o decisiones
  ya tomadas: pregunte.
- Tras una corrección del usuario, anote la lección donde se aplicará: la skill que corresponde
  o «Cuidados al trabajar aquí».
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
