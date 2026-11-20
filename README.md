# TAU | Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática

TAU es el sistema de información de la Carrera de Matemática (CMAT) y su Instituto de
Investigación Matemática (IIMAT), FCPN, UMSA. Reúne en un solo lugar la actividad científica
(productos, actividades, proyectos, líneas de investigación), la gestión académica (planes de
estudio, oferta por gestión, asignación docente, carga horaria) y el Sistema Interno de Aseguramiento
de la Calidad (SIAC) de la Carrera. Cada hecho se registra una sola vez y, con eso, se generan los CV, los informes de
proyecto, la memoria anual y los informes de calidad. Hecho con [FastHTML](https://fastht.ml),
HTMX, MonsterUI y SQLite.

Nació en 2026 como «Portal de Investigación» del IIMAT. Los nombres técnicos son `TAU_*` (variables de entorno),
`tau.db` (la base), el servicio `tau` y la aplicación `tau` de Fly.io; hasta el 17-nov-2026 llevaban «portal».

| Documento | Para qué |
|---|---|
| [Plan del manual de usuario](docs/manual-plan.md) | El manual de usuario **no se distribuye con el repositorio** (decisión del 17-nov-2026): el repositorio trae el texto del manual del sistema (`instancias/ejemplo/manual/`, que se arma con `scripts/manual.py`) y cada instancia suma sus capítulos; el de la Carrera de Matemática vive en `instancias/cmat/manual/`. La referencia vigente es la guía de uso |
| [Guía de uso](docs/guia-de-uso.md) | Referencia completa para cada rol: docentes e investigadores, direcciones, Comisión de calidad, estudiantes y administración |
| [Importaciones](docs/importaciones.md) | Todas las cargas de datos (CSV, DOI, arXiv, BibTeX, OpenAlex): campos, claves de unión y orden de carga |
| [Mantenimiento](docs/mantenimiento.md) | Para TI: cómo está armado, recetas (migraciones, pantallas, estilos, dependencias), operación y problemas frecuentes |
| [Despliegue](docs/despliegue.md) | Instalación en un servidor propio, correo, respaldos, mudanzas y actualizaciones |
| [Despliegue en Fly.io](docs/despliegue-fly.md) | Alternativa sin servidor propio, y cómo mudarse después a uno |
| [Guía del piloto](docs/piloto.md) | Piloto con usuarios reales: grupos escalonados, datos previos y su responsable, tareas por rol y opiniones. **En pausa desde el 15-nov-2026** |
| [Gobernanza](docs/gobernanza.md) | Lo que se acuerda fuera del código: exportaciones de la DTIC, titularidad, alojamiento de datos, respaldo |
| [Decisiones de IA](docs/ia/decisiones.md) | Diseño de la IA con criterio humano: niveles de datos, funciones vedadas, revisión y medición |
| [PLAN.md](PLAN.md) | Diseño, reglas de negocio, estado y **todas las decisiones con fecha** (la sección 72 es la vigente) |

## Qué hace

- **Acceso:** cuentas con invitación por correo o contraseña temporal, recuperación de
  contraseña, bloqueo por intentos fallidos, carga masiva desde CSV, categoría de cada investigador(a).
- **Perfil:** datos, identificadores (ORCID, MathSciNet, zbMATH, arXiv…), áreas MSC2020, foto,
  resumen con LaTeX; directorio interno y perfil público opcional.
- **Productos y actividades:** autores del instituto y externos, nivel de revisión e índices,
  detección de duplicados, adjuntos, clasificación MSC2020 (sugerida desde zbMATH Open); importación
  desde DOI (Crossref), arXiv y BibTeX.
- **Proyectos:** individuales (los crea cada investigador) e institucionales (propuesta anual en la
  convocatoria de septiembre, con decisión de la administración y continuidad); participantes, objetivos y flujo *propuesta → aprobación* de actividades y
  productos, con bandeja de pendientes y avisos por correo.
- **Informes:** CV, informe de proyecto (con el plan de actividades de los institucionales) y memoria del
  instituto por año, periodo octubre–septiembre o rango, imprimibles; descargas XLSX, CSV y BibTeX.
- **Docencia:** planes de estudio, oferta y asignación docente por gestión, carga horaria, preparación del semestre.
- **Estudiantes y egresados** (complementan a Seguimiento Académico; sin materias ni notas): cohortes de ingreso, egreso,
  titulación y deserción cargadas desde un CSV (alimentan los indicadores de progresión); portal del estudiante
  con ingreso por enlace al correo; actividad estudiantil con verificación; encuestas anónimas o nominales con enlace personal;
  tutoría con reuniones confidenciales; egresados con seguimiento a los 6 meses, 1, 3 y 5 años, directorio opcional y mentoría;
  y un informe de seguimiento estudiantil con solo cifras agregadas.
- **Servicios** (PLAN §58, §67 y §70): comunicados y eventos con convocados; convocatorias a auxiliaturas según el reglamento
  de auxiliares vigente (postulación en línea, comisión, calificación por formulario, designación e impresos); perfil y
  proyecto de grado con tutor, tribunal, observaciones y plantilla LaTeX; banco de temas, oportunidades, biblioteca,
  buzón, apoyo y orientación para estudiantes.
- **Para cada persona** (PLAN §67–§69): «Mis pendientes» y calendario del docente y del investigador, preferencias de
  oferta, programas analíticos, lista de curso, evaluación docente anónima, historial y certificados, acceso abierto y
  colaboraciones; el estudiante tiene su plan de estudios, tutoría, encuestas y servicios.
- **Aseguramiento de la Calidad (SIAC, PLAN §57 y §72):** marco de calidad propio, indicadores con su base, evidencias con
  huella, autoevaluación, plan de mejora con actividades, reprogramaciones y cortes trimestrales, ficha estadística y
  página pública de indicadores. Sin nombres de agencias acreditadoras.
- **IA con criterio humano** (PLAN §59): funciones apagadas por omisión que solo proponen borradores; nada surte efecto
  sin la aprobación de una persona.
- **Administración:** cuentas, roles, auditoría, piloto y adopción. **API JSON** de solo lectura para perfiles públicos.
  Página pública de privacidad (`/publico/privacidad`).

## Puesta en marcha (desarrollo)

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # instala dependencias
uv run python scripts/seed.py --reset    # base con datos de ejemplo (con el servidor detenido)
uv run python main.py                    # http://127.0.0.1:5001, con recarga automática
uv run pytest                            # ~1.060 pruebas, unos 10 minutos (+50 en navegador con --navegador)
```

`seed.py` sin `--reset` solo agrega lo que falte. En desarrollo los correos no se envían: quedan
como archivos `.eml` en `data/correos/` y se abren con cualquier cliente de correo.

### Cuentas de ejemplo

Son solo para la base de ejemplo. Las administradoras (admin y Sofía) tienen Administración del sistema y Dirección del
Instituto; ninguna tiene Dirección de Carrera, Coordinación académica ni Comisión de calidad. Para probar esas pantallas,
asígnelos en «Usuarios → Roles» o use `--rol` de la skill `captura-visual`.

| Correo | Contraseña | Perfil |
|---|---|---|
| admin@instituto.test | `Admin-portal-2026` | Administradora |
| sofia.kovalevskaya@instituto.test | `Temporal-2026` (temporal) | Investigadora y administradora; responsable de un proyecto |
| emmy.noether@instituto.test | `Temporal-2026` (temporal) | Investigadora; responsable de un proyecto con propuestas pendientes |
| alan.turing@instituto.test | `Temporal-2026` (temporal) | Investigador; tiene propuestas pendientes y una rechazada |
| srinivasa.ramanujan@instituto.test | `Temporal-2026` (temporal) | Investigador con el perfil vacío |

Las contraseñas temporales se cambian en el primer ingreso. Emmy y Alan tienen productos y
actividades de ejemplo, incluido un artículo en coautoría (un solo registro, visible en ambos
perfiles).

## Estructura

```
main.py                        create_app(): fast_app, MonsterUI, Beforeware, routers, manejo de errores
app/
  comun/                       base que usan todos los módulos
    config.py                  configuración (variables de entorno TAU_*)
    db.py                      fastlite + fastmigrate; función SQL sin_tildes; auditar()
    seguridad.py               Argon2, contraseñas temporales, política de contraseñas
    auth.py                    Beforeware de sesión y de origen (CSRF), login, cambio y recuperación de contraseña
    usuarios.py                cuentas y límite de intentos de ingreso
    adjuntos.py                archivos adjuntos validados por contenido (los usan todos los módulos)
    modulos.py                 módulos del sistema: registro, estado, compuerta de rutas y puntos de extensión (PLAN §73)
    calendario.py              pendientes y fechas de una persona: junta lo que aporta cada módulo activo
    importar_usuarios.py       carga masiva de cuentas desde CSV
    tokens.py                  enlaces de un solo uso (recuperar contraseña, invitación)
    correo.py                  envío de correo (archivo .eml, SMTP, memoria para pruebas)
    unidades.py                jerarquía UMSA › FCPN › CMAT › IIMAT
    permisos.py                roles con alcance y vigencia; puede(usuario, accion, unidad)
    vinculos.py                historial de vínculo con el Instituto o la Carrera (categoría y jornada por periodo)
    academicos.py              la persona académica: grados, personas sin acceso
    importar_vinculos.py       carga del historial de vínculos desde un CSV de Recursos Humanos
    personas.py                autores y participantes: 'i:<id>', 'e:<id>' y provisionales 'n:…'
    estudiantes.py             periodos de estudio de estudiantes y tesistas; indicadores de participación
    paises.py                  países normalizados: variantes, códigos ISO y deducción desde afiliaciones
    fotos.py                   recorte y limpieza de fotos (Pillow)
    adscripcion.py             cargo y «unidad o grupo» calculados de cada persona
    importar_grados.py         carga de grados académicos desde CSV
    notificaciones.py          centro de avisos y resumen semanal
    privacidad.py              qué datos se guardan, quién los ve y cuánto se conservan (aviso y /publico/privacidad)
    piloto.py                  comentarios por pantalla y adopción por rol durante el piloto
    xlsx_plantilla.py          llenar plantillas XLSX ajenas sin alterarlas (solo las celdas pedidas)
    componentes/               layout (página, navegación, modal), registros (insignias, filtros, datos, fechas),
                               grados, recursos (static), errores
    rutas/                     admin_usuarios/ (paquete: cuentas, importar_cuentas, importar_grados, roles, ficha,
                               vinculo, historial), admin_auditoria, avisos, estudiantes, mis_datos, piloto
  investigacion/               producción y proyectos de investigación
    perfiles.py                perfil, áreas MSC, completitud y directorio
    identificadores.py         ORCID, MathSciNet, zbMATH, arXiv, Scholar: validación y enlaces
    msc.py                     catálogo MSC2020: búsqueda y clasificación de los productos
    lineas.py                  líneas de investigación institucionales con vigencia
    catalogos.py               tipos de actividad y de producto e índices administrables (del sistema o agregados)
    actividades.py             actividades y participantes
    productos.py               productos, autores, reglas de revisión e informe, DOI/arXiv, citas
    filiacion.py               filiación IIMAT/UMSA por autor: detección y declaración
    proyectos.py               proyectos, permisos y flujo propuesta → aprobación
    institucionales.py         proyectos institucionales: periodos, convocatorias, propuestas y vigencia
    avisos.py                  avisos por correo del flujo de proyectos
    revistas.py                catálogo de revistas con indexación por año (ISSN, clasificación)
    importar_revistas.py       carga del catálogo de revistas por CSV
    importacion.py             importación desde Crossref y arXiv; reconocimiento de autores; MSC de zbMATH Open
    openalex.py                consulta a OpenAlex: obras por ORCID y citas
    cosecha.py                 carga de la producción desde OpenAlex y actualización de citas
    bibtex.py                  importar y exportar BibTeX
    carga_proyectos.py         carga horaria de los participantes en proyectos institucionales
    mis_pendientes.py          «Mis pendientes» y calendario del investigador (no guardan nada)
    acceso_abierto.py          declaración propia de acceso abierto y datos de cada producto
    coautores.py               colaboraciones derivadas de productos y proyectos (no guardan nada)
    componentes/               perfil, selector de autores y participantes, líneas, registros (adjuntos y
                               vinculación a proyectos)
    rutas/                     perfil, investigadores, actividades, bibtex, adjuntos, propuestas, publico (+ API),
                               personas (coautores externos), coautores, mis_pendientes, acceso_abierto,
                               admin_revistas, admin_lineas, admin_catalogos
      proyectos/               un módulo por pestaña: lista, datos, resumen, participantes, registros,
                               pendientes, plan, reasignar y ficha (registrada al final)
      productos/               lista, formulario, carga_openalex y ficha (registrada al final)
  informes/                    informes de investigación (PLAN §73; hasta el 16-nov-2026, dentro de calidad/)
    informes.py                datos de CV, informe de proyecto y memoria; exportación CSV/XLSX
    anexo.py                   informe de I+D+i (/informes/investigacion), por tema y año
    programados.py             informes que se envían solos en fechas fijas
    calidad_datos.py           tablero de calidad de datos (/informes/calidad)
    estudiantes.py             estudiantes en la investigación: tesis e indicadores de participación
  calidad/                     Aseguramiento de la Calidad (SIAC de la Carrera, PLAN §57)
    marco.py                   marco de calidad: dimensiones, criterios, indicadores, atributos y metas (/calidad/marco)
    marco_csv.py               carga del marco de calidad desde la instancia (calidad/marco-carrera/)
    indicadores.py             cifras de los indicadores: cálculos automáticos, manuales, cierres (/calidad/indicadores)
    evidencias.py              evidencias por criterio con huella SHA-256 (/calidad/evidencias; archivos en <datos>/evidencias)
    autoevaluacion.py          autoevaluación: juicios por criterio, síntesis, informe (/calidad/autoevaluaciones)
    mejora.py                  plan de mejora: acciones, avisos de plazo, evaluaciones externas (/calidad/mejora)
    actividades_mejora.py      actividades de cada acción: avances con evidencia, cumplimiento, reprogramaciones y aprobación del plan
    cortes_mejora.py           cortes trimestrales de seguimiento (congelan el estado) e informe del corte
    importar_mejora.py         carga del plan de mejora desde CSV (calidad/plan-de-mejora.csv de la instancia)
    importar_capacitacion.py   carga de capacitaciones desde CSV
    listados.py                listados de la ficha estadística (una fila por persona, asignatura, producto…)
    publico.py                 página pública de indicadores (/publico/indicadores)
    ficha.py                   ficha estadística y llenado de plantillas XLSX por correspondencia (/calidad/ficha)
    capacitacion.py            capacitación del personal (/calidad/capacitacion)
    convenios.py               convenios y sus actividades (/calidad/convenios)
    impacto.py                 impacto de los proyectos de interacción social (/calidad/impacto)
    estudiantes.py             tesis e indicadores de participación de estudiantes
    cuerpo_academico.py        carga docente e indicadores del cuerpo académico
    calidad_datos.py           calidad de los datos: lo que falta completar y a quién avisar
    seguimiento_estudiantil.py anexo de seguimiento estudiantil: cohortes, actividad, encuestas, tutoría y egresados (agregados)
    rutas/                     un módulo por pantalla: informes, anexo, marco, indicadores, evidencias, autoevaluacion,
                               mejora, actividades_mejora, cortes_mejora, importar_mejora, ficha, capacitacion,
                               convenios, impacto, cuerpo_academico, calidad_datos, seguimiento_estudiantil, publico
  academico/                   docencia y currículo
    planes.py                  programas, planes de estudio, asignaturas, electivas, requisitos, observaciones
    reformas.py, malla.py,     ciclo de vida de los planes (PLAN §65): reforma curricular, malla editable (o por CSV),
    menciones.py,              menciones, equivalencias con los planes que reemplaza y puesta en vigencia y cierre
    equivalencias.py, vigencia.py
    importar_planes.py         carga de planes de estudio desde la instancia (planes/)
    gestiones.py               gestiones académicas: I, INV, II y VER de cada año
    semestre.py, cambios.py    ciclo de vida de la gestión (PLAN §66): activar, concluir, reabrir; cambios con fecha y motivo
    oferta.py                  oferta por gestión y paralelo, asignación docente y horas
    carga.py                   carga horaria por semestre
    preparacion.py             preparación del semestre: qué falta para empezarlo
    importar_oferta.py         carga de la oferta de gestiones pasadas desde CSV
    docente.py, historial.py   «Mis pendientes», calendario, historial y certificados del docente (PLAN §68)
    preferencias.py            preferencias del docente para la oferta
    programas.py               programa analítico por asignatura y gestión
    listas.py                  lista de estudiantes por paralelo (copia temporal o API de Kardex)
    evaluacion.py              evaluación docente anónima
    rutas/                     planes, malla, equivalencias, programas, vigencia, oferta, carga, preparacion, renovaciones, listas,
                               evaluacion, preferencias, mi_docencia, mis_pendientes, historial (/docencia/…)
  estudiantil/                 seguimiento estudiantil (PLAN §49 y §50)
    cohortes.py                cohortes de ingreso, egreso, titulación y deserción (ciclos I y II)
    importar.py                carga del CSV de Seguimiento Académico (vista previa y aplicar)
    actividad.py               actividad estudiantil declarada: tipos, validación, verificación y avisos
    tutoria.py                 tutoría: asignación de tutores, reuniones confidenciales y cifras agregadas
    encuestas.py               motor de encuestas: armado, invitaciones por correo, respuesta con enlace y resultados
    plantillas_encuesta.py     encuestas de partida (satisfacción, bienestar, abandono, egresados, perfil de egreso)
    rendimiento.py             vacantes de admisión y rendimiento agregado por asignatura (sin RU ni notas)
    mi_plan.py, calendario.py  «Mi plan de estudios» (marcas privadas) y calendario del estudiante (PLAN §67)
    apoyo.py, orientacion.py   apoyo estudiantil (señales calculadas y casos) y bienestar y orientación
    rutas/                     cohortes (/docencia/cohortes: tablero y carga), rendimiento (vacantes y rendimiento),
                               actividades (verificación), estudiante (/estudiante: portal del estudiante), mi_plan,
                               calendario, mi_tutoria, mi_apoyo, mis_encuestas, evaluacion, orientacion, apoyo,
                               tutoria (/tutoria y /docencia/tutoria), encuestas (/docencia/encuestas),
                               responder (/encuesta/<enlace>, pública)
  egresados/                   egresados (PLAN §50)
    egresados.py               titulación, hitos de seguimiento (6 meses, 1, 3 y 5 años), invitaciones programadas e indicadores
    directorio.py              directorio opcional de egresados, invitación y solicitudes de mentoría
    empleadores.py             registro de empleadores, destinatarios de la encuesta a empleadores
    rutas/                     egresados (/docencia/egresados), empleadores (/docencia/empleadores), directorio (/estudiante/directorio, /estudiante/perfil-egresado)
  ia/                          IA con criterio humano (PLAN §59): la IA sugiere y la persona decide
    servicio.py                única puerta a los modelos: vedados, niveles de datos, seudonimización, proveedores, revisión
    funciones.py               catálogo de funciones activables y módulos vedados
    clasificacion.py           nivel (0 a 3) de cada dato que puede alimentar a la IA
    catalogo.py                las 7 funciones y los datos que recibe cada una (memoria, informe de proyecto, resumen del CV,
                               clasificar un producto, síntesis de encuesta, autoevaluación, sugerir evidencias)
    textos.py                  cifras desde la base ({{marcadores}}) y sin citas textuales de las respuestas
    medicion.py                resultados del piloto, decisiones de cierre y reporte de sesgos
    instrucciones/             instrucciones versionadas por función (<clave>/v<n>.md)
    rutas/                     /ia (Uso de IA en TAU), /ia/admin, /ia/usos, /ia/sesgos, /ia/guia y el panel de revisión
  servicios/                   servicios para estudiantes y personal (PLAN §58)
    comunicados.py             comunicados, convocatorias y eventos con convocados, confirmación y asistencia
    auxiliaturas.py            convocatorias a auxiliaturas: requisitos, ítems, tribunal 2 + 2, postulación, fases y resultado
    grado.py                   perfil y documento final: tutor, tribunal, revisiones de 15 días hábiles, resolución y defensa
    latex.py                   ZIP en LaTeX del perfil (clase perfil-cmat) y nota de presentación
    rubricas.py, designaciones.py,  auxiliaturas según el reglamento vigente (PLAN §70): formularios de calificación,
    formularios.py                  resultado, designación e impresos
    temas.py, oportunidades.py,     banco de temas de grado, oportunidades, biblioteca y recursos (PLAN §67)
    recursos.py
    rutas/                     comunicados, auxiliaturas, designaciones, formularios, grado, temas, oportunidades,
                               recursos (/servicios/… y /estudiante/…)
  inicio.py                    página de inicio: junta los pendientes y cifras que aporta cada módulo activo
  busqueda.py                  búsqueda global: junta los grupos que aporta cada módulo activo
  navegacion.py                menú lateral y pestañas del teléfono: junta los ítems que aporta cada módulo (PLAN §53)
  manifiestos.py               catálogo de módulos: junta el modulo.py de cada paquete (PLAN §73)
static/css/tailwind.css        estilos de Tailwind compilados (scripts/estilos.sh a partir de estilos/)
static/vendor/                 htmx, fasthtml.js, Franken UI y KaTeX con versión fija (sin CDN)
instancias/ejemplo/            instancia de ejemplo: una carrera ficticia y chica (unidades, catálogos, un plan, un marco de calidad)
instancias/cmat/               (no se versiona) instancia de la Carrera de Matemática: sus planes 2017, su marco de calidad,
                               su plan de mejora y el catálogo MSC2020 (CC BY-NC-SA 4.0). La usan el seed y las pruebas que dependen de ella
app/instalacion.py             carga de una instancia en una base nueva (scripts/instalar.py; PLAN §74)
migrations/0001-esquema.sql    esquema base, sin datos de ninguna unidad; las migraciones siguientes parten de él
scripts/seed.py                datos de ejemplo
scripts/crear_admin.py         primer administrador en producción
scripts/manual.py              manual de usuario de una instancia: capturas sobre datos de demostración y PDF (manual/ de la instancia)
scripts/instancia_demo.py      qué instancia usan el seed, el manual y las mediciones (instancias/cmat si existe, si no la de ejemplo; o TAU_INSTANCIA)
scripts/paquete.py             exportar e importar todos los datos (base, fotos, adjuntos, evidencias): respaldos y mudanzas
scripts/restaurar_prueba.sh    simulacro de restauración sobre una base temporal (docs/mantenimiento.md §5.3)
scripts/medir.py               rendimiento de las pantallas y GET que escriben (docs/mantenimiento.md §5.11)
scripts/estilos.sh             recompilar Tailwind (el tema de colores no se compila: lo sirve /tema.css desde app/comun/marca.py)
scripts/iniciar.sh             arranque en contenedor (con Litestream si hay réplica configurada); como-tau.sh: ejecutar
                               un script como el usuario del contenedor
Dockerfile, fly.toml,
litestream.yml                 imagen de contenedor y configuración para Fly.io
docs/                          guía de uso, guía de mantenimiento, guías de despliegue (servidor propio y Fly.io) y planes (módulos, instancia, manual)
tests/                         pytest con el TestClient de Starlette; tests/navegador/ con Playwright
```

Dependencias: `comun` no importa nada de los demás paquetes; `investigacion`, `calidad`, `academico`, `estudiantil`,
`egresados`, `servicios` e `ia` pueden usar `comun` (`calidad` usa `estudiantil` para el seguimiento estudiantil y
`egresados` usa `estudiantil` para el motor de encuestas; `servicios` usa `investigacion` para los adjuntos y `estudiantil`
para la cuenta del estudiante). Los módulos vedados para la IA (auxiliaturas, grado, oferta, carga y tutoría) no importan
`app.ia`. `app/inicio.py`, `app/navegacion.py` y `main.py` reúnen todo.

## Configuración

Variables de entorno (en producción, ver [despliegue](docs/despliegue.md)):

| Variable | Por defecto | Uso |
|---|---|---|
| `TAU_DB` | `data/tau.db` | Base SQLite. Fotos, adjuntos y correos van en `fotos/`, `adjuntos/` y `correos/` junto a ella |
| `TAU_URL` | `http://localhost:5001` | Dirección pública, para los enlaces de los correos y la protección CSRF |
| `TAU_ORIGENES_EXTRA` | — | Otras direcciones desde las que se usa el sistema, separadas por coma (p. ej. una interna); protección CSRF |
| `TAU_SECRET_KEY` | archivo `.sesskey` | Clave de firma de la cookie de sesión |
| `TAU_HTTPS_ONLY` | `0` | `1` en producción: cookie solo por HTTPS |
| `TAU_MAX_CUERPO_MB` | `25` | Tamaño máximo de un envío; uno mayor recibe 413 (el adjunto mayor es de 20 MB) |
| `TAU_SISTEMA` | `TAU` | Nombre corto del sistema (encabezado, título de las páginas, correos, exportaciones) |
| `TAU_SISTEMA_DESCRIPCION` | Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática | Descripción (ingreso, correos) |
| `TAU_INSTITUTO` | Instituto de Investigación Matemática | Nombre del instituto en informes y memoria. Vacía, se usa el nombre de Administración → Unidades; con valor, manda la variable |
| `TAU_CARRERA` | Carrera de Matemática | Nombre de la Carrera (membrete, informes, correos). Vacía, se usa el nombre de Administración → Unidades; con valor, manda la variable |
| `TAU_FACULTAD` | Facultad de Ciencias Puras y Naturales | Facultad a la que pertenece la Carrera (membrete). Vacía, se usa el nombre de Administración → Unidades; con valor, manda la variable |
| `TAU_UNIVERSIDAD` | Universidad Mayor de San Andrés | Universidad a la que pertenece el instituto. Vacía, se usa el nombre de Administración → Unidades; con valor, manda la variable |
| `TAU_DIRECCION` | (vacío) | Dirección, teléfonos y sitio de la Carrera para el pie del membrete de los informes, en una línea |
| `TAU_ZONA_HORARIA` | `America/La_Paz` | Zona horaria de plazos, vigencias y horas mostradas (la base guarda UTC) |
| `TAU_MONEDA` | `BOB` | Moneda de los montos de proyectos (se muestra como «Bs») |
| `TAU_PAIS` | `Bolivia` | Las revistas de este país son «nacionales» en los informes |
| `TAU_OPENALEX_CLAVE` | — | Clave de OpenAlex (opcional; OpenAlex contabiliza el uso y la clave permite superar el cupo gratuito) |
| `TAU_OPENALEX_URL` | `https://api.openalex.org` | Dirección de la API de OpenAlex (solo para pruebas o un espejo) |
| `TAU_IA_LOCAL_URL`, `TAU_IA_LOCAL_MODELO` | — | Modelo de IA local con API compatible con OpenAI (p. ej., Ollama en `http://127.0.0.1:11434/v1`); PLAN §59 |
| `TAU_LISTAS_URL`, `TAU_LISTAS_CLAVE`, `TAU_LISTAS_TIEMPO_S` | — | API del sistema de notas (Kardex) para la lista de estudiantes por paralelo; sin ella se usa la copia temporal que carga la Dirección; PLAN §68 |
| `TAU_IA_EXT_URL`, `TAU_IA_EXT_MODELO`, `TAU_IA_EXT_CLAVE` | — | Proveedor de IA externo (opcional) |
| `TAU_IA_EXT_ZDR` | `false` | `true` declara retención cero de datos; sin ella, el proveedor externo no se usa |
| `TAU_IA_TIEMPO_S` | `300` | Límite de cada llamada a la IA, en segundos |
| `TAU_EXIGIR_REVISTA_VERIFICADA` | `0` | `1` para la acreditación: solo cuentan artículos en revistas verificadas del catálogo |
| `TAU_FILIACIONES` | IIMAT; CMAT; FCPN; UMSA y sus nombres completos | Nombres que cuentan como filiación del instituto al importar (separados por «;»). Vacía, la sigla y el nombre de cada unidad de Administración → Unidades |
| `TAU_CONTACTO` | (vacío) | Correo que se informa a Crossref al importar |
| `TAU_CORREO_MODO` | `archivo` | `archivo`, `smtp` (con cola persistente y reintentos, `docs/mantenimiento.md` §5.5) o `desactivado` (las pruebas usan `memoria`) |
| `TAU_CORREO_REMITENTE` | `TAU <no-responder@instituto.test>` | Remitente |
| `TAU_SMTP_HOST` / `_PUERTO` / `_USUARIO` / `_CLAVE` | `localhost` / `587` / — / — | Servidor SMTP |
| `TAU_SMTP_STARTTLS` | `1` | `0` para desactivar STARTTLS |
| `TAU_SOLO_LECTURA` | `0` | `1` durante mudanzas o mantenimiento: se consulta, pero no se guardan cambios |
| `TAU_INSTANCIA` | `instancias/ejemplo` | Carpeta con los datos y la marca de la unidad (PLAN §74): la carga `scripts/instalar.py` y de ella salen la marca y los parámetros mientras el sistema corre. En desarrollo con el seed: `instancias/cmat` |
| `TAU_PERFIL` | `minimo` | Módulos con que arranca una base **nueva**: `minimo`, `instituto`, `carrera`, `carrera_instituto` o `completo`. Después manda Administración → Módulos (PLAN §73) |
| `TAU_PILOTO` | `0` | `1` durante el piloto con usuarios reales: cada pantalla lleva «Comentar esta pantalla» (`docs/piloto.md`) |
| `TAU_INFORMES_PROGRAMADOS` | `1` | `0` desactiva los informes que se envían solos (las pruebas lo usan) |
| `TAU_REGISTROS` | `archivo` | `archivo`: consola y `data/registros/tau.log` (con rotación); `consola`: solo consola |
| `TAU_AVISO_ERRORES` | (vacío) | Correo que recibe un aviso de cada error del servidor (a lo más uno cada 15 min) |

## Pruebas

`uv run pytest`. Cada prueba usa una base nueva en un directorio temporal. Los correos quedan en
memoria (`app.correo.ENVIADOS`, fixture `buzon`) y las consultas a Crossref, arXiv y zbMATH se simulan
(`tests/test_importacion.py`), así que las pruebas no necesitan red.

**Pruebas en navegador** (`tests/navegador/`, Playwright): `uv run pytest --navegador`. Recorren
en Chrome los flujos críticos (ingreso y salida, registrar un producto, proponer y decidir una
propuesta institucional, generar y descargar el anexo) y fallan si la página registra errores de
JavaScript, recursos que no cargan o violaciones de la CSP. Sin `--navegador` se omiten.
- Levantan el sistema en un puerto libre con una base temporal (`tests/navegador/preparar.py`); no
  tocan `data/tau.db` ni el servidor de desarrollo.
- Usan Google Chrome instalado. Sin Chrome: `uv run playwright install chromium` y
  `PLAYWRIGHT_CANAL= uv run pytest --navegador`.
- Para ver el navegador: `--headed --slowmo 300`.

**Integración continua** (`.github/workflows/pruebas.yml`): en cada push a `main` y en cada pull request, GitHub
Actions instala exactamente `uv.lock`, corre `ruff` y `pytest --navegador` con el Chrome del runner (el límite del
trabajo es de 45 minutos; con ~1.100 pruebas conviene vigilar que no se acerque).
El resultado aparece junto al commit en GitHub. Las acciones y las versiones de uv y ruff van fijadas.

## Migraciones

Para cambiar el esquema, agregue `migrations/NNNN-descripcion.sql` con el número siguiente (receta en
`docs/mantenimiento.md` §4.1). Los datos de una unidad no van en una migración: van en su instancia (PLAN §74). Nunca edite una migración ya aplicada: fastmigrate registra en la base
la versión aplicada y ejecuta solo las nuevas al arrancar.

## Convenciones

**HTMX**
- **Sin herencia de atributos** (`htmx.config.disableInheritance`): cada elemento declara su
  `hx-target` y `hx-swap`. Un botón dentro de un contenedor con `hx-swap="outerHTML"` no lo hereda.
- **Refrescos por evento:** tras guardar, el servidor responde con `HX-Trigger`
  (`productos-cambiados`, `actividades-cambiadas`, `pendientes-cambiados`) y las listas, fichas y
  contadores que lo escuchan se recargan solos.
- **Filas de tabla fuera de banda** (`hx-swap-oob`) siempre dentro de `<template>`.
- **URL de las vistas filtradas:** la fija el servidor con `HX-Replace-Url`
  (`HtmxResponseHeaders(replace_url=url_filtrada("/pagina", q=q, …))`), para que apunte a la página y no al
  fragmento; la página completa lee los mismos parámetros, de modo que recargar o compartir el enlace muestra lo mismo.
- **Errores:** a HTMX se le responde con el código (403, 404…) y el navegador muestra un aviso
  (`app/comun/componentes/errores.py`). A las peticiones normales, una página con el estilo del sistema.
- **Modales:** el servidor responde con `modal(...)` dentro de `#modal`; cerrar es vaciarlo (botones con
  `**CERRAR`, Escape o un clic fuera). El cuadro lleva `role="dialog"` nombrado por su título;
  `acciones.js` pone el foco en el primer campo, lo retiene dentro con Tab y lo devuelve a quien lo abrió.
- **Errores de formulario:** use `mensaje_error(...)`: un resumen con `role="alert"` que recibe el foco al
  llegar en una respuesta (en un formulario largo no queda fuera de la vista).
- **Envíos:** mientras dura una petición que no es GET, su botón (o los de envío del formulario) queda
  deshabilitado; `boton_espera` agrega el ícono girando, para las que tardan.
- **Confirmar o deshacer:** `hx-confirm` abre el diálogo propio de `acciones.js` (botón con el verbo de la
  pregunta, rojo si destruye algo). Para lo reversible, en lugar de confirmar, responda con
  `aviso_con_deshacer(sess, mensaje, hx_post=…, hx_vals=…)` (`componentes/avisos_emergentes.py`), cuya
  petición debe ser explícita e idempotente (p. ej., `activo=1`, no «alternar»).
- **Navegación** (`app/navegacion.py`, PLAN §53): menú lateral agrupado y plegable en pantallas grandes; en el
  teléfono, pestañas abajo y «Más», que abre el mismo menú. Cada módulo aporta sus ítems (`menu` y `menu_estudiante` en
  `app/<paquete>/aportes.py`, con grupo y orden; PLAN §73): una pantalla nueva entra al menú ahí, con la misma condición
  de permiso que su ruta, y `navegacion.py` solo junta los de los módulos activos. `layout.py` solo dibuja (`comun` no importa
  de los otros paquetes): `main.py` le entrega `MENU` y `MENU_MOVIL`.
- **Búsqueda global** (`app/busqueda.py`): un grupo nuevo es una función `(q, auth, límite)` en `BUSQUEDA` del
  `aportes.py` de su paquete, que debe filtrar por lo que la persona puede abrir. Los pendientes y las cifras del inicio
  (`app/inicio.py`) entran igual: `inicio` y `cifras` en `aportes.py`.

**Tablas**
- Una `<table data-tabla="nombre-del-archivo">` gana orden por columna, filtro por texto y «Descargar
  CSV» de lo visible (`static/js/tablas.js`, sin librerías). Las columnas sin título no se ordenan ni
  se exportan; una celda puede traer `data-valor` para ordenar por otro valor. Con
  `data-tabla-filtro="no"` se omite el filtro (listas con buscador propio del servidor). Úselo en
  tablas de datos con varias filas; no en tablas por grupos (p. ej., un plan por semestre).

**Rutas y archivos**
- **Descargas sin extensión en la URL** (`/informes/memoria/xlsx`, no `.xlsx`): convención de
  cuando la ruta estática de FastHTML capturaba las URL terminadas en extensiones conocidas. Esa
  ruta ya no existe: los archivos estáticos se sirven solo en `/static`.
- **Estilos:** Tailwind está compilado en `static/css/tailwind.css`. Al usar una clase nueva, ejecute
  `scripts/estilos.sh` (instrucciones en el propio script) y confirme el CSS; `tests/test_estilos.py`
  falla si falta. Las clases que MonsterUI arma en tiempo de ejecución van en
  `estilos/clases_dinamicas.txt`. Librerías de terceros en `static/vendor/`, con versión fija
  (`app/comun/componentes/recursos.py`).
- Rutas con segmento literal que choca con `{id}` (p. ej. `/productos/bibtex` frente a
  `/productos/{pid}`) se registran antes: ver el orden de routers en `main.py`.
- Fotos y adjuntos se guardan fuera de `static/`, con nombre aleatorio, y se sirven por rutas que
  verifican permisos.

**Seguridad**
- La autorización se verifica en el servidor en cada ruta; ocultar un botón no basta.
- Sin sesión solo se accede a `/login`, `/recuperar…`, `/acceso…` (enlace de ingreso del estudiante),
  `/encuesta/<enlace>`, `/publico/…`, `/api/v1/…` y `/salud` (`RUTAS_PUBLICAS` en `app/comun/auth.py`). Una cuenta de
  estudiante solo llega a `/estudiante`, `/avisos`, `/logout` y `/piloto` (`RUTAS_ESTUDIANTE`).
- Toda ruta comprueba algo (un permiso, la cuenta, la ficha del estudiante): `tests/test_rutas_declaradas.py` falla con
  una ruta sin control reconocible; las que son para todo el personal van en su lista, con el motivo.
- **Roles y permisos** (`app/comun/permisos.py`): cada acción la permiten ciertos roles, en su unidad
  (`puede(usuario, accion, unidad)`); las rutas `/admin` se autorizan con `REGLAS_ADMIN` en
  `app/comun/auth.py`, y lo que no está ahí se deniega.
- Las exportaciones CSV/XLSX neutralizan fórmulas (`=`, `+`, `-`, `@`) para evitar su ejecución en Excel.
- **CSRF:** toda petición que modifica datos (POST, PUT, PATCH, DELETE) debe venir del propio sistema
  según `Origin` (o `Referer`): el host de la petición, `TAU_URL` o `TAU_ORIGENES_EXTRA`
  (`app/comun/auth.py`, `beforeware_origen`). Complementa la cookie `SameSite=Lax`, que no protege de
  otros subdominios del mismo sitio (p. ej. `*.umsa.bo`). Sin tokens: los formularios no cambian.
- **Cabeceras y CSP** (`app/comun/cabeceras.py`): solo recursos del propio sistema, sin conexiones a
  otros sitios ni incrustación en marcos. `script-src 'self'` estricto: sin scripts en línea ni
  `eval`. El HTML no lleva `onclick`, `hx-on` ni `<script>` en línea; los comportamientos se declaran
  con atributos `data-accion`, `data-navegar`, etc., que atiende `static/js/acciones.js` (ver su
  encabezado). htmx corre con `allowEval: false`. `tests/test_csp.py` lo vigila.

## Partes públicas y API

Lo público se limita a quienes activaron «Perfil público» en «Mi perfil» y a los indicadores que la Dirección de Carrera
marcó como públicos en el marco de calidad (solo años cerrados, sin cifras con base menor que 5: `app/calidad/publico.py`).

| Ruta | Contenido |
|---|---|
| `/publico/investigadores` | Directorio público (búsqueda por nombre, unidad o área) |
| `/publico/investigadores/{id}` | Perfil: cargo, áreas MSC, resumen, publicaciones, identificadores |
| `/publico/indicadores` | Indicadores de calidad de la Carrera: valor, base, meta y fórmula de los años cerrados |
| `/publico/privacidad` | Qué datos guarda el sistema, para qué, quién los ve y cuánto se conservan |
| `GET /api/v1/investigadores` | Lista JSON de perfiles públicos (`?q=` para buscar) |
| `GET /api/v1/investigadores/{id}` | Perfil público con sus productos |
| `GET /api/v1/productos` | Productos aceptados o publicados con algún autor de perfil público (`?anio=`) |

La API responde con `Access-Control-Allow-Origin: *`, así la web del instituto puede consumirla.

## Repositorio

El código está en <https://github.com/manumath/tau>. No se versionan `data/` (la base y los correos de desarrollo),
`.sesskey`, `.venv/`, los PDF de agencias (`iac-cinda/`), las políticas de la UMSA (`politicas/`) ni los logos originales (`static/img/membrete/logo_*`): el
membrete usa la marca de la instancia (`instancias/<nombre>/marca/`) o, si no la trae, la genérica de `static/img/marca/` (PLAN §74). Los commits usan el correo `noreply` de GitHub del autor.
**Aún no tiene archivo `LICENSE`**: hasta que se agregue, el código se puede leer pero no hay permiso para reutilizarlo.

## Licencias de datos

El catálogo MSC2020 (`MSC2020.tsv`, en la instancia de quien lo use) es de Mathematical Reviews y zbMATH Open, bajo
CC BY-NC-SA 4.0: no se distribuye con el sistema. Los logos de una unidad son de esa unidad y van en su instancia.
