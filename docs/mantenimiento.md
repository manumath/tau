# Guía de mantenimiento

Para quien mantiene TAU (Sistema Integrado de Gestión Académica y Científica de la Carrera de
Matemática): el personal de TI del IIMAT y la persona que acompaña la
implementación. Supone que conoce Python y HTML; no supone que conozca FastHTML ni htmx.

Otros documentos:

- `README.md`: qué hace el sistema, estructura de archivos, configuración (`PORTAL_*`) y convenciones.
- `PLAN.md`: las decisiones y el porqué de cada regla, por sección (p. ej., sección 12 filiación,
  14 revistas, 21 líneas de investigación, 22 plan de ampliación).
- `docs/despliegue.md` y `docs/despliegue-fly.md`: instalación en un servidor propio o en Fly.io.
- `docs/guia-de-uso.md`: el sistema visto por investigadores y administración.
- `CLAUDE.md` y `.claude/skills/`: lo que debe saber un asistente de IA (Claude Code) que trabaje en
  el código, y sus procedimientos: cerrar una etapa, nueva migración, nueva ruta o permiso, capturas
  de pantalla (`.claude/skills/captura-visual/capturar.py` también sirve sin asistente).

## 1. El primer día

Requisitos: macOS o Linux, [uv](https://docs.astral.sh/uv/), Python 3.13 (uv lo instala) y
Google Chrome (solo para las pruebas en navegador).

```sh
uv sync                                   # dependencias, incluidas las de desarrollo
uv run python scripts/seed.py             # base de ejemplo en data/portal.db, con cuentas de demostración
uv run python main.py                     # http://127.0.0.1:5001
uv run pytest                             # ~400 pruebas, un minuto
uv run pytest --navegador                 # además, 5 flujos en Chrome
```

`scripts/seed.py` imprime las cuentas de demostración y su contraseña temporal. Es idempotente:
se puede ejecutar de nuevo sin duplicar datos; `--reset` borra la base de desarrollo y empieza de cero.

Recorrido sugerido para conocer el código (una tarde):

1. `main.py`: cómo se arma la aplicación (encabezados, Beforeware, routers).
2. `app/comun/auth.py`: ingreso, sesión y la verificación de origen (CSRF).
3. `app/investigacion/productos.py` y `app/investigacion/rutas/productos/`: un área completa, de
   las reglas a las pantallas.
4. `app/investigacion/institucionales.py`: el flujo de propuestas institucionales, el más complejo.
5. `tests/test_productos.py` y `tests/navegador/test_flujos.py`: cómo se prueba.

## 2. Cómo está armado

```
navegador ──HTML──▶ htmx (static/vendor) ──petición──▶ uvicorn
                                                        │
  CabecerasSeguridad (CSP, nosniff…) ◀──────────────────┤ middleware (app/comun/cabeceras.py)
  /static/* ──▶ archivos de static/ (sin sesión)        │
                                                        ▼
  Beforeware, en orden: origen (CSRF) · solo lectura · sesión y permisos · mantenimiento
                                                        │
                                                        ▼
  rutas (app/*/rutas/)  ──▶  reglas (app/*/*.py)  ──▶  app/comun/db.py  ──▶  SQLite
  devuelven HTML            validan y guardan          dialecto SQL,
  (componentes FastHTML)                               transacciones
```

- **Una petición = una función.** Cada ruta (`@rt("/productos/{pid}")` con `get`, `post`, `put` o
  `delete`) devuelve HTML hecho con componentes de Python (`Div`, `Form`…, y los de MonsterUI).
  htmx lo inserta en la página según `hx-target` y `hx-swap`. No hay API interna ni JavaScript
  propio salvo lo mínimo (avisos, KaTeX).
- **Las reglas no van en las rutas.** Validaciones, permisos de negocio y cálculos están en los
  módulos (`productos.py`, `institucionales.py`, `vinculos.py`…), que no importan nada de la
  interfaz y se prueban sin navegador. Las rutas leen el formulario, llaman al módulo y arman la
  respuesta.
- **Paquetes:**

  | Paquete | Contiene |
  |---|---|
  | `app/comun` | Configuración, base de datos, cuentas, seguridad, correo, personas, vínculos, estudiantes, países, componentes de interfaz y recursos estáticos |
  | `app/investigacion` | Perfiles, producción, actividades, proyectos, propuestas institucionales, revistas, OpenAlex, líneas |
  | `app/acreditacion` | Memoria, CV, informes y anexo de I+D+i para IAC-CINDA |
  | `app/academico` | Vacío: docencia y currículo (fase 3 del plan de ampliación) |

  `comun` no importa de los demás paquetes (desde la fase 2); `app/inicio.py` reúne las tarjetas de
  todos los módulos en la página de inicio.
- **Dónde buscar una regla:**

  | Pregunta | Dónde |
  |---|---|
  | ¿Cuenta este producto para el informe? | `productos.cuenta_para_informe`, `filiacion.estado_producto`, `vinculos` |
  | ¿Quién puede editar o aprobar en un proyecto? | `proyectos.puede_gestionar`, `proyectos.rol_de` |
  | ¿Cuándo rige un proyecto institucional? | `institucionales.refrescar_vigencias` |
  | ¿Cómo se clasifica un artículo por su revista? | `revistas.clasificacion` |
  | ¿Con qué unidad está vinculada una persona? | `app/comun/vinculos.py` (siempre con `unidad`; sin ella, el IIMAT), `app/comun/unidades.py` |
  | ¿Quién puede hacer qué? | `ROLES` y `ACCIONES` en `app/comun/permisos.py`; se decide con `puede(usuario, accion, unidad)` |
  | ¿Qué rutas son públicas? | `RUTAS_PUBLICAS` en `app/comun/auth.py` |
  | ¿Qué cifras lleva la memoria o el anexo? | `app/acreditacion/informes.py`, `app/acreditacion/anexo.py` |

- **Tareas periódicas:** no hay programador de tareas. La vigencia de los proyectos institucionales
  y los recordatorios de continuidad se recalculan en la primera petición de cada hora
  (`_mantenimiento` en `main.py`).

## 3. Convenciones que conviene no romper

Las de htmx, rutas y seguridad están en el README («Convenciones»). Además:

- **Idioma:** código, comentarios y mensajes en español; la interfaz trata al usuario de «usted».
- **Fechas:** hora de La Paz (`main.py` fija `TZ`). En SQL use `HOY`, `AHORA`, `vigente_hasta()` y
  `marca_tiempo()` de `app/comun/db.py`, nunca `date('now')` directamente.
- **Transacciones:** varias escrituras que van juntas, dentro de `with transaccion():`.
- **Auditoría:** toda acción que cambia datos de otros o de configuración llama a
  `auditar(usuario_id, accion, entidad, id, detalle)`.
- **Permisos en el servidor:** ocultar un botón no basta; la ruta verifica. Cada ruta `/admin/*`
  necesita una regla en `REGLAS_ADMIN` (`app/comun/auth.py`), o queda cerrada para todos
  (`tests/test_permisos_rutas.py` lo comprueba). Dentro de las rutas y reglas de negocio se usa
  `permisos.puede(usuario, accion, unidad)`; no hay otra marca de administración.
- **Estilos:** clases de Tailwind y de Franken UI (`uk-…`). Una clase de Tailwind nueva exige
  recompilar (sección 4.4).
- **Cada cambio con su prueba.** Una regla nueva, una prueba en `tests/`; un flujo nuevo de
  pantallas críticas, considere una en `tests/navegador/`.

## 4. Recetas

### 4.1 Agregar una migración

1. Cree `migrations/NNNN-descripcion.sql` con el número siguiente (hoy la última es la 0033). Un
   comentario inicial dice qué hace y por qué (con la sección de `PLAN.md`).
2. SQL de SQLite. Para columnas nuevas, `ALTER TABLE … ADD COLUMN`; si la tabla necesita cambios
   que SQLite no admite, cree la tabla nueva, copie y renombre.
3. Datos iniciales (catálogos) en la misma migración, con `INSERT`.
4. `uv run pytest`: `test_migraciones_aplicadas` comprueba que se aplicó.
5. Si los datos de ejemplo deben reflejarla, agregue un paso idempotente en `scripts/seed.py`.

**Nunca edite una migración ya aplicada** en algún servidor: la base guarda el número de la última
aplicada y no vuelve a leerla. Los cambios van en una migración nueva. Las migraciones se aplican
solas al arrancar el sistema.

### 4.2 Agregar una pantalla o una ruta

1. Elija el paquete (`comun`, `investigacion`, `acreditacion` o `academico`) y el archivo de
   `rutas/`; si es un área nueva, un archivo nuevo con `rt = APIRouter()`, y regístrelo en la tupla
   de routers de `create_app` en `main.py`.
2. **Orden:** una ruta literal que choca con una variable (`/productos/nuevo` frente a
   `/productos/{pid}`) debe registrarse antes. En los paquetes `proyectos/` y `productos/`, la
   ficha se registra al final (ver su `__init__.py`).
3. La lógica en el módulo del paquete, no en la ruta. Valide y devuelva el formulario con los
   errores (`mensaje_error`) o redirija (`Redirect`) y avise (`add_toast`).
4. Si la página es pública, agregue su patrón exacto a `RUTAS_PUBLICAS`. Si es de administración,
   agregue su regla a `REGLAS_ADMIN` y, si hace falta, una acción nueva a `permisos.ACCIONES` (con
   una fila en la matriz de `tests/test_permisos_rutas.py`).
5. Pruebe con `TestClient` (fixtures `app`, `client`, `login`, `HX` y `buzon` de `tests/conftest.py`).

### 4.3 Agregar un campo a un registro

Migración (4.1) → validación en el módulo (`validar`/`preparar`) → formulario y ficha en la ruta →
exportaciones e informes que deban mostrarlo (`app/acreditacion/informes.py`) → prueba.

### 4.4 Estilos: una clase de Tailwind nueva

Los estilos están compilados en `static/css/tailwind.css`. Si usa una clase que no estaba
(`tests/test_estilos.py` lo detecta y nombra el archivo y la línea):

```sh
scripts/estilos.sh          # la primera vez, el script explica cómo obtener la herramienta
```

y confirme el CSS en el mismo commit. Las clases que MonsterUI arma en tiempo de ejecución
(`md:{…}`, `grid-cols-{n}`) van en `estilos/clases_dinamicas.txt`. Evite dos clases que fijan la
misma propiedad en un elemento (p. ej., `border-border` y `border-amber-300`): gana la que aparezca
después en el CSS, no la que usted espera.

### 4.5 Actualizar una librería de `static/vendor/`

htmx, fasthtml.js, Franken UI y KaTeX tienen versión fija (`VERSIONES` en
`app/comun/componentes/recursos.py`). Para actualizar una:

1. Lea las notas de la versión (cambios incompatibles).
2. Descargue los mismos archivos de la versión nueva desde `cdn.jsdelivr.net/npm/<paquete>@<versión>/…`
   y reemplácelos (las URL de origen están en el historial de git del commit que los agregó).
3. Actualice `VERSIONES`.
4. `uv run pytest --navegador` y revise a ojo las páginas principales en modo claro y oscuro.

Las URL llevan una huella del contenido (`?v=…`): los navegadores toman la versión nueva sin
vaciar caché.

### 4.6 Actualizar dependencias de Python

FastHTML y MonsterUI están en versiones 0.x/1.0: pueden cambiar su API entre versiones menores.
`uv.lock` fija las versiones exactas; hoy: python-fasthtml 0.14.13, monsterui 1.0.47, fastlite
0.2.4, fastmigrate 0.5.3, starlette 1.7.0, uvicorn 0.53.0.

Política:

- **Cuándo:** una vez por semestre, o antes si hay un aviso de seguridad (Starlette, uvicorn,
  argon2-cffi, Pillow y openpyxl son las más expuestas).
- **Cómo:** un paquete a la vez, en una rama:
  ```sh
  uv lock --upgrade-package python-fasthtml
  uv sync
  uv run pytest --navegador
  ```
  Lea las notas de la versión antes. Si algo falla y no es obvio, vuelva a la versión anterior
  (`git checkout uv.lock && uv sync`) y anótelo.
- **FastHTML en particular:** el sistema depende de detalles suyos: la tupla `before` de
  Beforeware, `APIRouter`, `fast_app(default_hdrs=False, …)` y la ruta estática genérica que
  `recursos.montar` quita. Tras actualizarlo, revise esos cuatro puntos.
- Una actualización de MonsterUI puede cambiar clases que arma en tiempo de ejecución: recompile
  los estilos (4.4) y ejecute las pruebas en navegador.

## 5. Operación

### 5.1 Desplegar una versión nueva

`docs/despliegue.md`, sección 8 (servidor propio) o `docs/despliegue-fly.md` (Fly.io). En corto:
respaldar, actualizar el código, `uv sync --no-dev`, reiniciar. Las migraciones se aplican al arrancar.

### 5.2 Respaldar y restaurar

Dos mecanismos, que se complementan:

- **Copia de la base** (`sqlite3 … ".backup …"` cada noche, o réplica continua con Litestream):
  ver `docs/despliegue.md`, sección 7.
- **Paquete completo** (base, fotos y adjuntos en un `.tar.gz`), para restaurar o mudarse:

  ```sh
  # Se puede ejecutar con el sistema en marcha.
  PORTAL_DB=/var/lib/portal/portal.db uv run python scripts/paquete.py exportar /respaldos/portal.tar.gz

  # Con el sistema DETENIDO. Si ya hay datos, exige --reemplazar y los mueve a
  # respaldo-previo-<fecha>/ junto a la base (no borra nada).
  PORTAL_DB=/var/lib/portal/portal.db uv run python scripts/paquete.py importar /respaldos/portal.tar.gz --reemplazar
  ```

**Ensayo de restauración (26 de septiembre de 2026)**, con una copia de la base de desarrollo:

| Paso | Resultado |
|---|---|
| Exportar con el sistema en marcha | Paquete de 0,3 MB; manifiesto con esquema v21 y conteos |
| Importar en una ubicación vacía | 5 cuentas, 7 productos, 3 actividades, 4 proyectos, 6 líneas: iguales al origen |
| Importar de nuevo sin `--reemplazar` | Se niega y explica qué hacer |
| Importar con `--reemplazar` | Datos anteriores movidos a `respaldo-previo-…`; importación completa |
| Importar un paquete antiguo (esquema v20) con el código actual | Aplica la migración 21 (crea las 6 líneas); el sistema arranca y responde |

**Repita el ensayo cada semestre** (y después de cambiar el procedimiento de respaldo) sobre una
copia, nunca sobre la base en uso. Un respaldo que nunca se restauró no es un respaldo. Anote aquí
la fecha y el resultado.

### 5.3 Modo solo lectura

`PORTAL_SOLO_LECTURA=1` deja el sistema consultable y rechaza todo cambio (útil durante una mudanza
o una restauración). No ejecuta las tareas horarias.

### 5.4 Correo

`PORTAL_CORREO_MODO`: `archivo` (por omisión, guarda cada correo como `.eml` en
`data/correos/`, útil para revisar sin enviar), `smtp` (producción; ver `PORTAL_SMTP_*`) o `memoria`
(pruebas).

## 6. Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| «Solicitud rechazada: no proviene del sistema» (403) al guardar | El sistema se abre con una dirección distinta de `PORTAL_URL` (otro dominio, IP, puerto) | Agregue esa dirección a `PORTAL_ORIGENES_EXTRA` |
| Una clase de Tailwind no se aplica | CSS sin recompilar | `scripts/estilos.sh` (4.4); `tests/test_estilos.py` lo señala |
| Nadie puede guardar nada | Modo solo lectura activo | Revise `PORTAL_SOLO_LECTURA` |
| Una cuenta no puede ingresar aunque la contraseña es correcta | Bloqueo por intentos fallidos (15 minutos) | «Usuarios» → desbloquear |
| El sistema no arranca tras actualizar | Falló una migración | Lea el error; restaure el respaldo previo (5.2) y corrija la migración en una nueva |
| Una página de administración responde 403 | A la cuenta le falta el rol | «Usuarios» → «Roles» (lo hace Administración del sistema) |
| Los correos no llegan | `PORTAL_CORREO_MODO` no es `smtp`, o credenciales SMTP | Revise `data/correos/` y la configuración SMTP |
| Una prueba en navegador falla solo en su equipo | Chrome no instalado o muy antiguo | `uv run playwright install chromium` y `PLAYWRIGHT_CANAL=` |

## 7. Deuda conocida

- **CSP no del todo estricta:** admite scripts en línea y `eval` por unos 50 manejadores `onclick`
  y `hx-on` en el HTML. Reemplazarlos por un script propio permitiría una política estricta.
- **fastlite** es solo para SQLite. Un cambio de motor necesitaría un adaptador para la API que se
  usa (`q`, `execute`, `t.<tabla>.insert/update`); el resto de lo propio de SQLite está en
  `app/comun/db.py` (ver su docstring).
- El mayor archivo de rutas es `app/investigacion/rutas/productos/formulario.py` (unas 480 líneas).
