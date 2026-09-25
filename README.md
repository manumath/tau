# Portal de Investigación

Portal del instituto para que cada investigador registre su actividad científica (productos,
actividades, proyectos) una sola vez y, con eso, se generen su CV, los informes de proyecto y la
memoria anual. Hecho con [FastHTML](https://fastht.ml), HTMX, MonsterUI y SQLite.

| Documento | Para qué |
|---|---|
| [Guía de uso](docs/guia-de-uso.md) | Cómo usar el portal: investigadores, responsables de proyecto y administración |
| [Despliegue](docs/despliegue.md) | Instalación en un servidor propio, correo, respaldos, mudanzas y actualizaciones |
| [Despliegue en Fly.io](docs/despliegue-fly.md) | Alternativa sin servidor propio, y cómo mudarse después a uno |
| [PLAN.md](PLAN.md) | Diseño, reglas de negocio, modelo de datos, estado, decisiones y pendientes |

## Qué hace

- **Acceso:** cuentas con invitación por correo o contraseña temporal, recuperación de
  contraseña, bloqueo por intentos fallidos, carga masiva desde CSV, categoría de cada investigador(a).
- **Perfil:** datos, identificadores (ORCID, MathSciNet, zbMATH, arXiv…), áreas MSC2020, foto,
  resumen con LaTeX; directorio interno y perfil público opcional.
- **Productos y actividades:** autores del instituto y externos, nivel de revisión e índices,
  detección de duplicados, adjuntos; importación desde DOI (Crossref), arXiv y BibTeX.
- **Proyectos:** individuales (los crea cada investigador) e institucionales; participantes, objetivos y flujo *propuesta → aprobación* de actividades y
  productos, con bandeja de pendientes y avisos por correo.
- **Informes:** CV, informe de proyecto y memoria anual imprimibles; descargas XLSX, CSV y BibTeX.
- **Administración:** cuentas, proyectos, auditoría. **API JSON** de solo lectura para perfiles públicos.

## Puesta en marcha (desarrollo)

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # instala dependencias
uv run python scripts/seed.py --reset    # base con datos de ejemplo (con el servidor detenido)
uv run python main.py                    # http://127.0.0.1:5001, con recarga automática
uv run pytest                            # 218 pruebas
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
  config.py                    configuración (variables de entorno PORTAL_*)
  db.py                        fastlite + fastmigrate; función SQL sin_tildes; auditar()
  seguridad.py                 Argon2, contraseñas temporales, política de contraseñas
  auth.py                      Beforeware de sesión, login, cambio y recuperación de contraseña
  usuarios.py                  cuentas y límite de intentos de ingreso
  importar_usuarios.py         carga masiva de cuentas desde CSV
  tokens.py                    enlaces de un solo uso (recuperar contraseña, invitación)
  correo.py                    envío de correo (archivo .eml, SMTP, memoria para pruebas)
  avisos.py                    avisos por correo del flujo de proyectos
  perfiles.py                  perfil, áreas MSC, completitud y directorio
  identificadores.py           ORCID, MathSciNet, zbMATH, arXiv, Scholar: validación y enlaces
  msc.py                       búsqueda en el catálogo MSC2020
  fotos.py                     recorte y limpieza de fotos (Pillow)
  personas.py                  autores y participantes: 'i:<id>', 'e:<id>' y provisionales 'n:…'
  actividades.py               actividades y participantes
  productos.py                 productos, autores, reglas de revisión e informe, DOI/arXiv, citas
  adjuntos.py                  adjuntos validados por contenido
  proyectos.py                 proyectos, permisos y flujo propuesta → aprobación
  importacion.py               importación desde Crossref y arXiv; reconocimiento de autores
  bibtex.py                    importar y exportar BibTeX
  informes.py                  datos de CV, informe de proyecto y memoria; exportación CSV/XLSX
  components/                  layout (página, navegación, modal), perfil, personas, registros, errores
  routes/                      un APIRouter por área: inicio, perfil, investigadores, actividades,
                               productos, bibtex, personas, adjuntos, proyectos, informes,
                               publico (+ API), admin_usuarios, admin_auditoria
catalogos/MSC2020.tsv          catálogo MSC2020 (CC BY-NC-SA 4.0; ver catalogos/README.md)
migrations/NNNN-*.sql|.py      migraciones versionadas; se aplican al arrancar
scripts/seed.py                datos de ejemplo
scripts/crear_admin.py         primer administrador en producción
scripts/paquete.py             exportar e importar todos los datos (base, fotos, adjuntos): respaldos y mudanzas
scripts/iniciar.sh             arranque en contenedor (con Litestream si hay réplica configurada)
Dockerfile, fly.toml,
litestream.yml                 imagen de contenedor y configuración para Fly.io
docs/                          guía de uso y guías de despliegue (servidor propio y Fly.io)
tests/                         pytest con el TestClient de Starlette
```

## Configuración

Variables de entorno (en producción, ver [despliegue](docs/despliegue.md)):

| Variable | Por defecto | Uso |
|---|---|---|
| `PORTAL_DB` | `data/portal.db` | Base SQLite. Fotos, adjuntos y correos van en `fotos/`, `adjuntos/` y `correos/` junto a ella |
| `PORTAL_URL` | `http://localhost:5001` | Dirección pública, para los enlaces de los correos |
| `PORTAL_SECRET_KEY` | archivo `.sesskey` | Clave de firma de la cookie de sesión |
| `PORTAL_HTTPS_ONLY` | `0` | `1` en producción: cookie solo por HTTPS |
| `PORTAL_INSTITUTO` | Instituto de Investigación Matemática | Nombre que muestra la interfaz |
| `PORTAL_CONTACTO` | (vacío) | Correo que se informa a Crossref al importar |
| `PORTAL_CORREO_MODO` | `archivo` | `archivo`, `smtp` o `desactivado` (las pruebas usan `memoria`) |
| `PORTAL_CORREO_REMITENTE` | `Portal de Investigación <no-responder@instituto.test>` | Remitente |
| `PORTAL_SMTP_HOST` / `_PUERTO` / `_USUARIO` / `_CLAVE` | `localhost` / `587` / — / — | Servidor SMTP |
| `PORTAL_SMTP_STARTTLS` | `1` | `0` para desactivar STARTTLS |
| `PORTAL_SOLO_LECTURA` | `0` | `1` durante mudanzas o mantenimiento: se consulta, pero no se guardan cambios |

## Pruebas

`uv run pytest`. Cada prueba usa una base nueva en un directorio temporal. Los correos quedan en
memoria (`app.correo.ENVIADOS`, fixture `buzon`) y las consultas a Crossref y arXiv se simulan
(`tests/test_importacion.py`), así que las pruebas no necesitan red.

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
  (`app/components/errores.py`). A las peticiones normales, una página con el estilo del portal.

**Rutas y archivos**
- **Descargas sin extensión en la URL** (`/informes/memoria/xlsx`, no `.xlsx`): la ruta de
  archivos estáticos de FastHTML captura cualquier URL terminada en extensiones conocidas.
- Rutas con segmento literal que choca con `{id}` (p. ej. `/productos/bibtex` frente a
  `/productos/{pid}`) se registran antes: ver el orden de routers en `main.py`.
- Fotos y adjuntos se guardan fuera de `static/`, con nombre aleatorio, y se sirven por rutas que
  verifican permisos.

**Seguridad**
- La autorización se verifica en el servidor en cada ruta; ocultar un botón no basta.
- Sin sesión solo se accede a `/login`, `/recuperar…`, `/publico/…` y `/api/v1/…` (reglas exactas
  en `app/auth.py`).
- Las exportaciones CSV/XLSX neutralizan fórmulas (`=`, `+`, `-`, `@`) para evitar su ejecución en Excel.

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
