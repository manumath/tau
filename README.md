# TAU | Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática

TAU es el sistema de información de la Carrera de Matemática (CMAT) y su Instituto de
Investigación Matemática (IIMAT), FCPN, UMSA. Reúne en un solo lugar la actividad científica
(productos, actividades, proyectos, líneas de investigación), la gestión académica (planes de
estudio, oferta por gestión, asignación docente, carga horaria) y la evidencia para la acreditación
ante IAC-CINDA. Cada hecho se registra una sola vez y, con eso, se generan los CV, los informes de
proyecto, la memoria anual y el anexo de acreditación. Hecho con [FastHTML](https://fastht.ml),
HTMX, MonsterUI y SQLite.

Nació en 2026 como «Portal de Investigación» del IIMAT; algunos nombres técnicos conservan
«portal» por compatibilidad con las instalaciones existentes (variables `PORTAL_*`, `portal.db`,
el servicio `portal` y la aplicación de Fly.io).

| Documento | Para qué |
|---|---|
| [Guía de uso](docs/guia-de-uso.md) | Cómo usar el sistema: investigadores, responsables de proyecto y administración |
| [Despliegue](docs/despliegue.md) | Instalación en un servidor propio, correo, respaldos, mudanzas y actualizaciones |
| [Despliegue en Fly.io](docs/despliegue-fly.md) | Alternativa sin servidor propio, y cómo mudarse después a uno |
| [PLAN.md](PLAN.md) | Diseño, reglas de negocio, modelo de datos, estado, decisiones y pendientes |

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
- **Administración:** cuentas, proyectos, auditoría. **API JSON** de solo lectura para perfiles públicos.

## Puesta en marcha (desarrollo)

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # instala dependencias
uv run python scripts/seed.py --reset    # base con datos de ejemplo (con el servidor detenido)
uv run python main.py                    # http://127.0.0.1:5001, con recarga automática
uv run pytest                            # 382 pruebas
```

`seed.py` sin `--reset` solo agrega lo que falte. En desarrollo los correos no se envían: quedan
como archivos `.eml` en `data/correos/` y se abren con cualquier cliente de correo.

### Cuentas de ejemplo

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
    config.py                  configuración (variables de entorno PORTAL_*)
    db.py                      fastlite + fastmigrate; función SQL sin_tildes; auditar()
    seguridad.py               Argon2, contraseñas temporales, política de contraseñas
    auth.py                    Beforeware de sesión y de origen (CSRF), login, cambio y recuperación de contraseña
    usuarios.py                cuentas y límite de intentos de ingreso
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
    componentes/               layout (página, navegación, modal), registros (insignias, filtros, datos, fechas),
                               grados, recursos (static), errores
    rutas/                     admin_usuarios/ (paquete: cuentas, importar_cuentas, roles, ficha, vinculo,
                               historial), admin_auditoria, estudiantes, mis_datos
  investigacion/               producción y proyectos de investigación
    perfiles.py                perfil, áreas MSC, completitud y directorio
    identificadores.py         ORCID, MathSciNet, zbMATH, arXiv, Scholar: validación y enlaces
    msc.py                     catálogo MSC2020: búsqueda y clasificación de los productos
    lineas.py                  líneas de investigación institucionales con vigencia
    actividades.py             actividades y participantes
    productos.py               productos, autores, reglas de revisión e informe, DOI/arXiv, citas
    filiacion.py               filiación IIMAT/UMSA por autor: detección y declaración
    adjuntos.py                adjuntos validados por contenido
    proyectos.py               proyectos, permisos y flujo propuesta → aprobación
    institucionales.py         proyectos institucionales: periodos, convocatorias, propuestas y vigencia
    avisos.py                  avisos por correo del flujo de proyectos
    revistas.py                catálogo de revistas con indexación por año (ISSN, clasificación)
    importar_revistas.py       carga del catálogo de revistas por CSV
    importacion.py             importación desde Crossref y arXiv; reconocimiento de autores; MSC de zbMATH Open
    openalex.py                consulta a OpenAlex: obras por ORCID y citas
    cosecha.py                 carga de la producción desde OpenAlex y actualización de citas
    bibtex.py                  importar y exportar BibTeX
    componentes/               perfil, selector de autores y participantes, líneas, registros (adjuntos y
                               vinculación a proyectos)
    rutas/                     perfil, investigadores, actividades, bibtex, adjuntos, propuestas, publico (+ API),
                               personas (coautores externos), admin_revistas, admin_lineas
      proyectos/               un módulo por pestaña: lista, datos, resumen, participantes, registros,
                               pendientes, plan, reasignar y ficha (registrada al final)
      productos/               lista, formulario, carga_openalex y ficha (registrada al final)
  acreditacion/                evidencia para IAC-CINDA
    informes.py                datos de CV, informe de proyecto y memoria; exportación CSV/XLSX
    anexo.py                   anexo de I+D+i para la acreditación, por criterio y año
    estudiantes.py             tesis e indicadores de participación de estudiantes
    guia_antecedentes.py       Guía de Antecedentes de IAC-CINDA: la plantilla oficial llenada con los datos
    rutas/                     informes, anexo, guia_antecedentes
  academico/                   docencia y currículo (fase 3)
    planes.py                  programas, planes de estudio, asignaturas, electivas, requisitos, observaciones
    importar_planes.py         carga de planes desde datos/planes/ (la usa la migración 0028)
    gestiones.py               gestiones académicas: I, INV, II y VER de cada año
    oferta.py                  oferta por gestión y paralelo, asignación docente y horas
    importar_oferta.py         carga de la oferta de gestiones pasadas desde CSV
    rutas/                     planes, oferta y gestiones (/docencia/…)
  inicio.py                    página de inicio: reúne tarjetas de todos los módulos

Dependencias: `comun` no importa nada de los demás paquetes; `investigacion`, `acreditacion` y
`academico` pueden usar `comun`. `app/inicio.py` y `main.py` reúnen todo.
static/css/tailwind.css        estilos de Tailwind compilados (scripts/estilos.sh a partir de estilos/)
static/vendor/                 htmx, fasthtml.js, Franken UI y KaTeX con versión fija (sin CDN)
datos/planes/                  planes de estudio en CSV (formato en su README)
catalogos/MSC2020.tsv          catálogo MSC2020 (CC BY-NC-SA 4.0; ver catalogos/README.md)
migrations/NNNN-*.sql|.py      migraciones versionadas; se aplican al arrancar
scripts/seed.py                datos de ejemplo
scripts/crear_admin.py         primer administrador en producción
scripts/paquete.py             exportar e importar todos los datos (base, fotos, adjuntos): respaldos y mudanzas
scripts/iniciar.sh             arranque en contenedor (con Litestream si hay réplica configurada)
Dockerfile, fly.toml,
litestream.yml                 imagen de contenedor y configuración para Fly.io
docs/                          guía de uso, guía de mantenimiento y guías de despliegue (servidor propio y Fly.io)
tests/                         pytest con el TestClient de Starlette
```

## Configuración

Variables de entorno (en producción, ver [despliegue](docs/despliegue.md)):

| Variable | Por defecto | Uso |
|---|---|---|
| `PORTAL_DB` | `data/portal.db` | Base SQLite. Fotos, adjuntos y correos van en `fotos/`, `adjuntos/` y `correos/` junto a ella |
| `PORTAL_URL` | `http://localhost:5001` | Dirección pública, para los enlaces de los correos y la protección CSRF |
| `PORTAL_ORIGENES_EXTRA` | — | Otras direcciones desde las que se usa el sistema, separadas por coma (p. ej. una interna); protección CSRF |
| `PORTAL_SECRET_KEY` | archivo `.sesskey` | Clave de firma de la cookie de sesión |
| `PORTAL_HTTPS_ONLY` | `0` | `1` en producción: cookie solo por HTTPS |
| `PORTAL_SISTEMA` | `TAU` | Nombre corto del sistema (encabezado, título de las páginas, correos, exportaciones) |
| `PORTAL_SISTEMA_DESCRIPCION` | Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática | Descripción (ingreso, correos) |
| `PORTAL_INSTITUTO` | Instituto de Investigación Matemática | Nombre del instituto en informes y memoria |
| `PORTAL_UNIVERSIDAD` | Universidad Mayor de San Andrés | Universidad a la que pertenece el instituto |
| `PORTAL_ZONA_HORARIA` | `America/La_Paz` | Zona horaria de plazos, vigencias y horas mostradas (la base guarda UTC) |
| `PORTAL_MONEDA` | `BOB` | Moneda de los montos de proyectos (se muestra como «Bs») |
| `PORTAL_PAIS` | `Bolivia` | Las revistas de este país son «nacionales» en los informes |
| `PORTAL_OPENALEX_CLAVE` | — | Clave de OpenAlex (opcional; OpenAlex contabiliza el uso y la clave permite superar el cupo gratuito) |
| `PORTAL_EXIGIR_REVISTA_VERIFICADA` | `0` | `1` para la acreditación: solo cuentan artículos en revistas verificadas del catálogo |
| `PORTAL_FILIACIONES` | IIMAT; CMAT; FCPN; UMSA y sus nombres completos | Nombres que cuentan como filiación del instituto al importar (separados por «;») |
| `PORTAL_CONTACTO` | (vacío) | Correo que se informa a Crossref al importar |
| `PORTAL_CORREO_MODO` | `archivo` | `archivo`, `smtp` o `desactivado` (las pruebas usan `memoria`) |
| `PORTAL_CORREO_REMITENTE` | `TAU <no-responder@instituto.test>` | Remitente |
| `PORTAL_SMTP_HOST` / `_PUERTO` / `_USUARIO` / `_CLAVE` | `localhost` / `587` / — / — | Servidor SMTP |
| `PORTAL_SMTP_STARTTLS` | `1` | `0` para desactivar STARTTLS |
| `PORTAL_SOLO_LECTURA` | `0` | `1` durante mudanzas o mantenimiento: se consulta, pero no se guardan cambios |
| `PORTAL_INFORMES_PROGRAMADOS` | `1` | `0` desactiva los informes que se envían solos (las pruebas lo usan) |

## Pruebas

`uv run pytest`. Cada prueba usa una base nueva en un directorio temporal. Los correos quedan en
memoria (`app.correo.ENVIADOS`, fixture `buzon`) y las consultas a Crossref, arXiv y zbMATH se simulan
(`tests/test_importacion.py`), así que las pruebas no necesitan red.

**Pruebas en navegador** (`tests/navegador/`, Playwright): `uv run pytest --navegador`. Recorren
en Chrome los flujos críticos (ingreso y salida, registrar un producto, proponer y decidir una
propuesta institucional, generar y descargar el anexo) y fallan si la página registra errores de
JavaScript, recursos que no cargan o violaciones de la CSP. Sin `--navegador` se omiten.
- Levantan el sistema en un puerto libre con una base temporal (`tests/navegador/preparar.py`); no
  tocan `data/portal.db` ni el servidor de desarrollo.
- Usan Google Chrome instalado. Sin Chrome: `uv run playwright install chromium` y
  `PLAYWRIGHT_CANAL= uv run pytest --navegador`.
- Para ver el navegador: `--headed --slowmo 300`.

## Migraciones

Para cambiar el esquema, agregue `migrations/000N-descripcion.sql` (o `.py` para cargar datos,
como `0004-msc2020.py`). Nunca edite una migración ya aplicada: fastmigrate registra en la base
la versión aplicada y ejecuta solo las nuevas al arrancar.

## Convenciones

**HTMX**
- **Sin herencia de atributos** (`htmx.config.disableInheritance`): cada elemento declara su
  `hx-target` y `hx-swap`. Un botón dentro de un contenedor con `hx-swap="outerHTML"` no lo hereda.
- **Refrescos por evento:** tras guardar, el servidor responde con `HX-Trigger`
  (`productos-cambiados`, `actividades-cambiadas`, `pendientes-cambiados`) y las listas, fichas y
  contadores que lo escuchan se recargan solos.
- **Filas de tabla fuera de banda** (`hx-swap-oob`) siempre dentro de `<template>`.
- **URL de las vistas filtradas:** la fija el servidor con `HX-Replace-Url`, para que apunte a la
  página y no al fragmento.
- **Errores:** a HTMX se le responde con el código (403, 404…) y el navegador muestra un aviso
  (`app/comun/componentes/errores.py`). A las peticiones normales, una página con el estilo del sistema.

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
- Sin sesión solo se accede a `/login`, `/recuperar…`, `/publico/…` y `/api/v1/…` (reglas exactas
  en `app/comun/auth.py`).
- **Roles y permisos** (`app/comun/permisos.py`): cada acción la permiten ciertos roles, en su unidad
  (`puede(usuario, accion, unidad)`); las rutas `/admin` se autorizan con `REGLAS_ADMIN` en
  `app/comun/auth.py`, y lo que no está ahí se deniega.
- Las exportaciones CSV/XLSX neutralizan fórmulas (`=`, `+`, `-`, `@`) para evitar su ejecución en Excel.
- **CSRF:** toda petición que modifica datos (POST, PUT, PATCH, DELETE) debe venir del propio sistema
  según `Origin` (o `Referer`): el host de la petición, `PORTAL_URL` o `PORTAL_ORIGENES_EXTRA`
  (`app/comun/auth.py`, `beforeware_origen`). Complementa la cookie `SameSite=Lax`, que no protege de
  otros subdominios del mismo sitio (p. ej. `*.umsa.bo`). Sin tokens: los formularios no cambian.
- **Cabeceras y CSP** (`app/comun/cabeceras.py`): solo recursos del propio sistema, sin conexiones a
  otros sitios ni incrustación en marcos. `script-src 'self'` estricto: sin scripts en línea ni
  `eval`. El HTML no lleva `onclick`, `hx-on` ni `<script>` en línea; los comportamientos se declaran
  con atributos `data-accion`, `data-navegar`, etc., que atiende `static/js/acciones.js` (ver su
  encabezado). htmx corre con `allowEval: false`. `tests/test_csp.py` lo vigila.

## Partes públicas y API

Lo público se limita a quienes activaron «Perfil público» en «Mi perfil».

| Ruta | Contenido |
|---|---|
| `/publico/investigadores` | Directorio público (búsqueda por nombre, unidad o área) |
| `/publico/investigadores/{id}` | Perfil: cargo, áreas MSC, resumen, publicaciones, identificadores |
| `GET /api/v1/investigadores` | Lista JSON de perfiles públicos (`?q=` para buscar) |
| `GET /api/v1/investigadores/{id}` | Perfil público con sus productos |
| `GET /api/v1/productos` | Productos aceptados o publicados con algún autor de perfil público (`?anio=`) |

La API responde con `Access-Control-Allow-Origin: *`, así la web del instituto puede consumirla.

## Licencias de datos

El catálogo MSC2020 (`catalogos/MSC2020.tsv`) es de Mathematical Reviews y zbMATH Open, bajo
CC BY-NC-SA 4.0; ver [catalogos/README.md](catalogos/README.md).
