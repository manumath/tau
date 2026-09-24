# Plan: Portal de Investigación del Instituto (FastHTML + HTMX)

## 1. Visión

Portal interno donde cada investigador inicia sesión con credenciales entregadas por el
instituto y mantiene al día su actividad científica. El mismo registro alimenta, sin
volver a escribirlo, tres salidas: el CV del investigador, la ficha de cada proyecto y
la memoria anual del instituto.

Principio rector: **cada hecho se registra una sola vez**. Un artículo con tres autores
del instituto es *un* producto enlazado a tres personas, no tres registros duplicados.
Un seminario de un proyecto aparece a la vez en el proyecto y en el perfil de quien lo dictó.

## 2. Actores y roles

| Rol | Cómo se obtiene | Qué puede hacer |
|---|---|---|
| **Administrador** (personal del instituto) | Rol global | Crea cuentas y proyectos, asigna responsables, restablece contraseñas, gestiona catálogos (tipos de actividad y producto), genera reportes institucionales |
| **Investigador** | Rol global (toda cuenta) | Edita su perfil; registra sus actividades y productos; ve los proyectos en que participa |
| **Responsable de proyecto** | Relación con un proyecto, no rol global | Edita el proyecto, gestiona participantes, aprueba o rechaza las propuestas de los participantes, agrega directamente actividades y productos al proyecto |
| **Participante de proyecto** | Relación con un proyecto | Ve el proyecto; desde su espacio personal registra actividades y productos y puede proponerlos al proyecto |
| **Participante externo** | Registro sin cuenta | No ingresa al sistema; figura como participante del proyecto, autor de productos o participante de actividades |

### 2.1 Flujo de propuesta y aprobación

Las actividades y productos siempre nacen en el **espacio personal** de quien los registra.
Al crearlos o editarlos, el investigador puede marcar uno o más proyectos en los que participa:

```
 Participante registra          Responsable del proyecto          Resultado
 ─────────────────────          ────────────────────────          ─────────
 actividad/producto  ──propone──▶  bandeja "Pendientes"  ──aprueba──▶  aparece en el proyecto
 (queda en su perfil)                                    ──rechaza──▶  vuelve con comentario;
                                                                        sigue en el perfil personal
```

- Mientras está **pendiente**, el registro es visible para quien lo propuso (con la etiqueta "pendiente en Proyecto X")
  y para los responsables del proyecto. No aparece en la ficha ni en los informes del proyecto.
- Al **aprobar**, el responsable puede asignar el **responsable de la actividad** entre los participantes del proyecto.
- Al **rechazar**, el comentario es obligatorio. El participante puede corregir y volver a proponer.
- Lo que el **responsable** registra y vincula a su propio proyecto queda aprobado de inmediato.
- Si un participante edita un registro ya aprobado, el cambio se aplica sin nueva aprobación, pero
  el responsable lo ve en la actividad reciente del proyecto. Además, puede desvincular el registro del proyecto en cualquier momento.
- Si un participante deja el proyecto, sus registros aprobados siguen en el proyecto, porque son historia del proyecto.
- El responsable ve un **contador de pendientes** en su tablero y en la pestaña del proyecto.

Propuesta de mejora: permitir **co-responsables** (proyectos con más de un investigador
principal son comunes) y que el administrador pueda **transferir la responsabilidad**.

## 3. Mejoras sobre la idea original

### 3.1 Propias del dominio matemático
- **Identificadores de autor**: ORCID, MR Author ID (MathSciNet), zbMATH, arXiv, Google Scholar.
- **Clasificación MSC2020** en perfiles, proyectos y productos (autocompletar con HTMX).
  Sirve para buscar especialistas y producir estadísticas por área.
- **LaTeX en resúmenes y títulos** mediante KaTeX en el cliente (`$\zeta(s)$` se muestra bien).
- **Importar por DOI** (Crossref) o **ID de arXiv** (API de arXiv): se pega el identificador,
  el formulario se rellena y el investigador confirma. Reduce mucho la carga de datos.
- **Importar y exportar BibTeX**, que el matemático ya usa.
- **Ciclo de vida de artículos**: en preparación → enviado → aceptado → publicado, con
  enlace preprint ↔ versión publicada (evita contar el mismo trabajo dos veces).

### 3.2 Gestión y calidad de datos
- **Autorías mixtas**: autores internos (enlace a la cuenta) y externos (texto libre con
  afiliación), con orden. El producto aparece en el perfil de cada autor interno.
- **Productos en varios proyectos**: un artículo puede agradecer a más de un proyecto.
- **Participantes externos sin cuenta**, reutilizables: una persona externa se registra una vez
  (nombre, institución, país, correo opcional) y se elige desde el autocompletar en proyectos,
  autorías y actividades, sin reescribirla cada vez. Si más adelante recibe cuenta, se fusiona con su usuario.
- **Detección de duplicados** por DOI, arXiv ID o título normalizado al crear un producto.
- **Registro de auditoría**: quién cambió qué y cuándo.
- **Adjuntos**: PDF de presentaciones, afiches y certificados de asistencia.

### 3.3 Salidas
- **CV exportable** (PDF/HTML) filtrado por período y tipo.
- **Ficha de proyecto** e **informe de avance** por período (útil ante agencias financiadoras).
- **Memoria anual del instituto**: productos y actividades registrados, agrupados por tipo y área, exportables a CSV y XLSX.
- **Perfil público opcional** (el investigador decide qué se publica) y vista pública de proyectos.

### 3.4 Cuenta y seguridad
- Contraseña inicial provista por el administrador, con **cambio obligatorio en el primer ingreso**.
- Hash con Argon2 (`argon2-cffi`), límite de intentos de login y bloqueo temporal.
- Restablecimiento por el administrador (MVP) y por correo (fase posterior).

## 4. Modelo de datos

```
usuario(id, email UNIQUE, nombres, apellidos, pass_hash, es_admin, activo,
        debe_cambiar_pass, creado_en, ultimo_acceso)
investigador(usuario_id PK →usuario, grado, cargo, unidad,
             orcid, mr_id, zbmath_id, arxiv_id, scholar_url, bio, perfil_publico)
intento_login(id, email, ip, exito, fecha)
investigador_msc(investigador_id, msc_codigo)

proyecto(id, codigo, nombre, descripcion, objetivo_general, fuente_financiamiento,
         monto, fecha_inicio, fecha_fin, estado{formulacion,vigente,finalizado})
proyecto_objetivo(id, proyecto_id, orden, texto)          -- objetivos específicos
persona_externa(id, nombres, apellidos, institucion, pais, email NULL, orcid NULL,
                usuario_id NULL →usuario)                  -- se enlaza si luego recibe cuenta

proyecto_participante(id, proyecto_id, investigador_id NULL, externo_id NULL,
                      rol{responsable,co_responsable,co_investigador,
                          postdoc,tesista,colaborador},
                      fecha_desde, fecha_hasta)
                      -- CHECK: exactamente uno de investigador_id / externo_id

tipo_actividad(id, nombre, activo)     -- seminario, congreso, escuela, visita, curso…
actividad(id, tipo_id, titulo, descripcion, fecha_inicio, fecha_fin, lugar,
          modalidad{presencial,virtual,hibrida}, ambito{local,nacional,internacional},
          creado_por →investigador, creado_en, actualizado_en)
actividad_participante(actividad_id, investigador_id NULL, externo_id NULL,
                       rol{organizador,expositor,asistente,comite})
actividad_proyecto(actividad_id, proyecto_id,
                   estado{pendiente,aprobado,rechazado},
                   responsable_participante_id NULL →proyecto_participante,
                   propuesto_por, propuesto_en,
                   revisado_por NULL, revisado_en NULL, comentario NULL)

tipo_producto(id, nombre, admite_revision, activo)  -- artículo, reporte de investigación, libro, preprint…
indice(id, nombre, cuenta_como_indexado, activo)     -- WoS, Scopus, SciELO, MathSciNet, zbMATH…
producto(id, tipo_id, titulo, resumen, anio, estado_publicacion,
         revision{indexado,arbitrado,sin_arbitraje}, revista_editorial,
         volumen, paginas, doi UNIQUE NULL, arxiv_id UNIQUE NULL, url,
         version_de_id NULL →producto, creado_por, creado_en, actualizado_en)
producto_autor(producto_id, orden, investigador_id NULL, externo_id NULL)
producto_proyecto(producto_id, proyecto_id,
                  estado{pendiente,aprobado,rechazado},
                  propuesto_por, propuesto_en,
                  revisado_por NULL, revisado_en NULL, comentario NULL)
producto_indice(producto_id, indice_id)
producto_msc(producto_id, msc_codigo)

msc(codigo, descripcion)                -- catálogo MSC2020 precargado
adjunto(id, entidad, entidad_id, nombre, ruta, mime, subido_por, fecha)
auditoria(id, usuario_id, accion, entidad, entidad_id, cambios_json, fecha)
```

Reglas de negocio que se validan en el servidor, no solo en la interfaz:
- `actividad_proyecto.responsable_participante_id` debe ser un participante del **mismo** proyecto.
  Como la actividad vive en una tabla de enlace, puede tener un responsable distinto en cada proyecto.
- Solo se puede proponer un registro a proyectos en los que quien lo propone es participante vigente.
- Solo un responsable o co-responsable del proyecto cambia `estado`. Si lo vincula él mismo, nace `aprobado`.
- Las fichas e informes de un proyecto consideran solo los enlaces con estado `aprobado`.
- Todo proyecto tiene al menos un participante con rol `responsable`.
- Una actividad o un producto lo edita su creador (y los autores internos, en el caso de productos).
  El responsable de un proyecto no edita el registro: lo aprueba, lo rechaza o lo desvincula.
- `fecha_fin >= fecha_inicio`.

## 5. Matriz de permisos

| Acción | Admin | Responsable | Participante | Otro investigador |
|---|---|---|---|---|
| Crear proyecto / asignar responsable | ✔ | — | — | — |
| Editar datos del proyecto | ✔ | ✔ | — | — |
| Agregar o quitar participantes | ✔ | ✔ | — | — |
| Vincular actividad o producto al proyecto | ✔ | ✔ (aprobado de inmediato) | proponer (queda pendiente) | — |
| Aprobar, rechazar o desvincular propuestas | ✔ | ✔ | — | — |
| Asignar responsable de actividad | ✔ | ✔ | — | — |
| Ver propuestas pendientes | ✔ | ✔ (todas) | ✔ (solo las propias) | — |
| Ver proyecto | ✔ | ✔ | ✔ | si es público |
| Editar perfil propio | ✔ | ✔ | ✔ | ✔ |

La autorización vive en funciones puras (`puede_editar_proyecto(user, proyecto)`) que se prueban aparte
y se llaman en cada ruta. Nunca basta con ocultar el botón.

## 6. Arquitectura técnica

### Stack
- **FastHTML** (Starlette + componentes FT en Python) y **HTMX** para la interactividad.
- **MonsterUI** (FrankenUI + Tailwind) para componentes con buen aspecto sin escribir CSS.
- **SQLite + fastlite**, con migraciones versionadas mediante **fastmigrate**. Migrar a
  PostgreSQL solo si hay concurrencia alta, lo que es poco probable en un instituto.
- **KaTeX** (CDN) para LaTeX; **httpx** para Crossref y arXiv; **bibtexparser**;
  **WeasyPrint** o **Typst** para los PDF; **openpyxl** para Excel.
- **pytest** con el cliente de pruebas de Starlette; **uv** para dependencias.

### Estructura propuesta
```
proyecto-fast/
├── main.py                  # fast_app(), Beforeware, montaje de routers
├── app/
│   ├── db.py                # conexión fastlite, dataclasses de tablas
│   ├── auth.py              # login, logout, cambio de contraseña, Beforeware
│   ├── permisos.py          # reglas de autorización (funciones puras)
│   ├── routes/              # un APIRouter por dominio
│   │   ├── perfil.py
│   │   ├── actividades.py
│   │   ├── productos.py
│   │   ├── proyectos.py
│   │   ├── admin.py
│   │   └── reportes.py
│   ├── components/          # FT reutilizables: tablas, formularios, modales, layout
│   └── services/            # crossref.py, arxiv.py, bibtex.py, exportar_cv.py
├── migrations/              # 0001-inicial.sql, 0002-…
├── static/
├── tests/
└── pyproject.toml
```

### Autenticación con FastHTML
- La sesión viaja en una cookie firmada (`session['uid']`). Una `Beforeware` redirige a
  `/login` si no hay sesión, excepto en `/login`, `/static` y las rutas públicas.
- Si `debe_cambiar_pass` está activo, la misma Beforeware obliga a pasar por `/cambiar-password`.
- Para peticiones HTMX con la sesión vencida, se responde con la cabecera `HX-Redirect: /login`
  en vez de insertar la página de login dentro de un fragmento.

## 7. Patrones HTMX por pantalla

| Pantalla | Patrón HTMX | Detalle |
|---|---|---|
| Listas (actividades, productos) | Búsqueda en vivo | `hx-get` + `hx-trigger="input changed delay:300ms"` sobre filtros de tipo, año y texto; reemplaza solo el `<tbody>` |
| Paginación | Scroll infinito o "cargar más" | `hx-trigger="revealed"` en la última fila |
| Perfil | Edición en línea | Clic en una sección → `hx-get` devuelve el formulario → `hx-put` devuelve la vista actualizada |
| Crear o editar registro | Modal | El formulario se carga en un `<dialog>`; al guardar, respuesta con **OOB swap** que inserta la fila en la tabla y cierra el modal |
| Autores de un producto | Filas dinámicas | "Agregar autor" hace `hx-get` de una fila nueva; buscador de investigadores internos con autocompletar |
| Responsable de actividad | Select dependiente | Al elegir proyecto, `hx-get` recarga el `<select>` solo con sus participantes |
| Importar DOI o arXiv | Autocompletado remoto | `hx-post` al servidor, que consulta Crossref y devuelve el formulario prellenado; `hx-indicator` muestra el spinner |
| Duplicados | Validación en vivo | Al salir del campo DOI o título, `hx-post` avisa si ya existe |
| Eliminar | Confirmación | `hx-delete` + `hx-confirm`, y la fila se quita con `hx-swap="outerHTML swap:300ms"` |
| Notificaciones | Toasts | `setup_toasts()` de FastHTML para "Guardado", "Propuesta enviada", "Sin permiso", etc. |
| Proponer a proyectos | Casillas en el formulario | El formulario de actividad o producto lista solo los proyectos del usuario; cada enlace muestra una insignia (pendiente, aprobado o rechazado) |
| Bandeja de pendientes | Aprobación en línea | Cada tarjeta tiene "Aprobar" y "Rechazar". Aprobar hace `hx-post` y la tarjeta desaparece; una actualización OOB descuenta el contador y agrega la fila a la pestaña del proyecto. Rechazar despliega un campo de comentario en la misma tarjeta |
| Contador de pendientes | Sondeo liviano | Insignia en la navegación con `hx-trigger="load, every 60s"` |
| Personas externas | Autocompletar con alta rápida | Busca entre las ya registradas; si no existe, "Crear externo" abre un mini formulario en línea |
| Tablero | Carga diferida | Cada tarjeta de indicadores con `hx-trigger="load"` |

Regla general: cada ruta devuelve la página completa si la petición es normal y solo el
fragmento si viene de HTMX (cabecera `HX-Request`). Así los enlaces funcionan también sin
JavaScript y se pueden marcar como favoritos.

## 8. Pantallas

1. **Login** y **cambio de contraseña**.
2. **Tablero personal**: resumen del año, proyectos, últimos registros, propuestas propias en espera o
   rechazadas y, si es responsable de algún proyecto, las propuestas que debe revisar.
3. **Mi perfil**: datos básicos, identificadores, áreas MSC y foto.
4. **Mis actividades** y **Mis productos**: tabla con filtros, creación en modal, proyectos vinculados
   con su estado, e importación desde DOI, arXiv o BibTeX.
5. **Mis proyectos**: lista con el rol del usuario en cada uno.
6. **Proyecto** (pestañas cargadas con HTMX): Resumen · Objetivos · Participantes · Actividades ·
   Productos · **Pendientes** (solo responsables) · Informe.
7. **Administración**: usuarios, proyectos, personas externas (incluida la fusión de duplicados), catálogos y auditoría.
8. **Reportes**: CV, informe de proyecto y memoria anual.

## 9. Fases de desarrollo

| Fase | Entregable | Contenido |
|---|---|---|
| **0. Base** | Esqueleto que corre | uv, `fast_app` con MonsterUI, layout y navegación, fastlite y primera migración, pytest, datos de prueba |
| **1. Acceso** | Login funcional | Usuarios, Argon2, Beforeware, cambio obligatorio de contraseña, administración básica de usuarios (crear, desactivar, restablecer) |
| **2. Perfil** | Investigador gestiona sus datos | Perfil con edición en línea, identificadores, MSC con autocompletar, foto |
| **3. Actividades y productos personales** | Núcleo del servicio | CRUD con modales, filtros, autorías mixtas, catálogos, adjuntos |
| **4. Proyectos** | Módulo de proyectos | Creación por el admin, edición por el responsable, participantes internos y externos, objetivos, **flujo de propuesta y aprobación**, bandeja de pendientes, responsable de actividad, permisos probados |
| **5. Productividad** | Menos tecleo | Importación DOI, arXiv y BibTeX; detección de duplicados; KaTeX |
| **6. Salidas** | Reportes | CV en PDF, informe de proyecto, memoria anual, exportación CSV y XLSX |
| **7. Extras** | Opcional | Perfiles públicos, restablecimiento y avisos por correo (por ejemplo, "tienes 2 propuestas por revisar"), auditoría visible, API JSON de solo lectura |
| **Futuro** | Si se requiere | Validación institucional (estado declarado o validado), inicio de sesión único (SSO o LDAP), integración con el repositorio institucional |

Las fases 0 a 4 forman el **MVP** que cubre la idea original. Las fases 5 y 6 son las que
más valor agregan para un instituto.

## 10. Despliegue y operación
- Uvicorn detrás de Caddy (HTTPS automático) en un servidor del instituto, o contenedor Docker.
- Respaldos continuos de SQLite con **Litestream**, o `sqlite3 .backup` diario.
- Variables de entorno para la clave de sesión y la configuración, sin secretos en el repositorio.
- Carga inicial desde una planilla de investigadores mediante un script de importación.

## 11. Decisiones tomadas (piloto)
- **Productos y nivel de revisión:** cada producto tiene `revision ∈ {indexado, arbitrado, sin_arbitraje}`.
  - Tipos que admiten revisión: artículos, capítulos, libros y actas.
  - Tipos siempre `sin_arbitraje` (`tipo_producto.admite_revision = 0`): reporte de investigación, preprint, presentación, etc.
  - Un producto `indexado` debe registrar al menos un índice (WoS, Scopus, MathSciNet, etc.) con
    `cuenta_como_indexado = 1`. Qué índices cuentan lo decide el instituto en el catálogo `indice`.
  - **Los informes del instituto consideran solo productos indexados o arbitrados.** El CV personal y
    la ficha del proyecto muestran todo, con un filtro.
- **Cuentas:** `usuario.es_admin` es un indicador. La cuenta es de investigador si tiene fila en
  `investigador`, así que un director puede ser investigador y administrador a la vez.
- **Participantes:** registran en su espacio personal y proponen al proyecto. El responsable aprueba y
  solo entonces el registro forma parte del proyecto (sección 2.1).
- **Externos:** sí hay participantes externos sin cuenta (tabla `persona_externa`).
- **Validación institucional:** no se requiere por ahora. Queda en "Futuro".
- **Integraciones (SSO o LDAP, repositorio):** no en el piloto. El login es local.

## 12. Avance
- **Iteración 1 (hecha):** fase 0 completa y fase 1 parcial.
  - Esqueleto uv, FastHTML y MonsterUI; migraciones con fastmigrate (`0001-usuarios`, `0002-catalogos`).
  - Login con Argon2 y límite de intentos; Beforeware; cambio obligatorio de la contraseña temporal.
  - Administración de usuarios: búsqueda en vivo, alta en modal con contraseña temporal, activar o desactivar, restablecer.
  - Tablero; datos de demostración; 26 tests.
- **Iteración 2 (hecha): fase 2, perfil del investigador.**
  - Catálogo MSC2020 oficial (6.603 códigos), cargado con una migración en Python.
  - «Mi perfil» con edición en línea por sección: datos básicos, identificadores de autor y
    resumen de investigación con LaTeX (KaTeX) y vista previa en vivo.
  - Identificadores validados y normalizados: el ORCID se comprueba con su dígito verificador y se
    acepta pegar la URL del perfil.
  - Áreas MSC con autocompletar por código o tema, área principal, hasta 10 áreas.
  - Foto recortada a 400×400 y sin metadatos (Pillow), servida solo con sesión.
  - Indicador de perfil completo en el perfil y en el tablero.
  - Directorio interno buscable por nombre, unidad o área, y perfil de solo lectura.
  - Búsquedas sin distinguir tildes ni mayúsculas (función `sin_tildes` registrada en SQLite).
  - Menú de usuario desplegable; 64 tests.
- **Iteración 3 (hecha): fase 3, actividades y productos.**
  - Personas externas reutilizables. Se dan de alta desde el mismo formulario y se reutilizan si
    ya existe alguien con igual nombre.
  - Actividades con participantes internos y externos, cada uno con su rol.
  - Productos con autores ordenables, nivel de revisión según el tipo e índices.
  - **Cuenta para el informe:** producto indexado o arbitrado, aceptado o publicado.
  - DOI y arXiv normalizados. Aviso de duplicado en vivo con la opción «Sumarme como autor».
  - Presentaciones vinculadas a su actividad.
  - Fichas de detalle con adjuntos (PDF, PNG o JPG validados por contenido), visibles solo para
    quien puede editar el registro.
  - Filtros con URL compartible; tablero con cifras del año; producción en el perfil público; 103 tests.
  - **Decisión:** un indexado o arbitrado *enviado* o *en preparación* aún no cuenta para el informe.
  - **Permisos:** editan el creador y los autores o participantes del instituto; elimina solo el creador.
- **Iteración 4 (hecha): fase 4, proyectos.**
  - La administración crea proyectos y asigna responsable. Responsables y co-responsables editan
    los datos y los objetivos, y gestionan participantes internos o externos (roles, bajas).
  - Siempre queda al menos un responsable. Solo la administración asigna o quita responsables, y
    los externos no pueden serlo.
  - **Flujo de aprobación:** «Vincular a proyectos» en los formularios de actividades y productos.
    - Lo que propone un participante queda pendiente; lo que vincula un responsable queda aprobado.
    - El responsable aprueba (y puede asignar el responsable de la actividad) o rechaza con motivo
      obligatorio.
    - Lo rechazado vuelve a proponerse al guardar el registro con la casilla marcada.
    - Una propuesta pendiente se retira desmarcando la casilla; lo aprobado solo lo desvincula un
      responsable.
  - Aviso «fuera del periodo del proyecto» en la bandeja.
  - «Editados después de aprobados» en el resumen del proyecto.
  - Al dar de baja a un participante, lo que ya estaba aprobado se conserva.
  - Contador de pendientes en la navegación, refrescado por evento y cada 60 s.
  - Pestañas con URL propia; tablero con cifras de proyectos; 124 tests.
- **Iteración 5 (hecha): fase 5, importación desde DOI y arXiv.**
  - Recuadro «Importar desde DOI o arXiv» en «Nuevo producto». Acepta identificadores o URL, y
    los DOI de arXiv (10.48550/…).
  - Consulta Crossref o arXiv y deja el formulario completo para revisar: tipo, título, autores,
    revista, año, volumen, número, páginas y resumen.
  - **Autores del instituto:** se reconocen por ORCID o por nombre (apellido o primer apellido,
    más la inicial), sin distinguir tildes.
  - **Externos:** se reutilizan los que ya existen. Los nuevos viajan como referencia provisional
    y se registran recién al guardar, así que cancelar no deja registros huérfanos.
  - **Preprint con versión publicada:** botón «Importar versión publicada», que trae el artículo
    por DOI y conserva el arXiv asociado.
  - Si el producto ya existe, el aviso ofrece «Sumarme como autor».
  - **Límite de arXiv:** una consulta cada 3 s; ante 406/429/503 reintenta una vez y luego
    explica el problema.
  - Red simulada en los tests; 146 tests.
  - **Pendiente de la fase 5:** importar y exportar BibTeX.
- **Iteración 6 (hecha): fase 6, informes.**
  - Menú «Informes» con tres documentos imprimibles: se ven como una hoja y el botón
    «Imprimir / Guardar PDF» usa el navegador, de modo que las fórmulas LaTeX salen bien.
    **Decisión:** no generar PDF en el servidor. WeasyPrint requiere librerías del sistema y
    ninguna de las dos alternativas entiende LaTeX.
  - **CV:** periodo configurable y opción «solo lo que cuenta». Agrupa en indexados,
    arbitrados, libros, en curso, reportes, preprints y presentaciones; luego actividades por
    tipo y proyectos. La persona aparece destacada en cada cita. La administración puede ver el
    CV de cualquier investigador.
  - **Informe de proyecto:** periodo configurable, solo lo aprobado; equipo, objetivos,
    productos (los que cuentan y los demás) y actividades con su responsable. Descarga en XLSX.
  - **Memoria anual** (solo administración): cifras, conteo por índice y por tipo de actividad,
    tabla por investigador y listados. Cada producto se cuenta una vez. Descarga en XLSX
    (4 hojas) y CSV (UTF-8 con BOM).
  - Protección contra inyección de fórmulas en planillas; 156 tests.
- **Pendiente de la fase 1:** vista de auditoría, página 403 con estilo, desbloqueo manual sin restablecer
  la contraseña, carga masiva de cuentas desde CSV.

## 13. Preguntas abiertas
1. ¿La agencia financiadora exige cuartiles (Q1–Q4) o factor de impacto de las revistas indexadas?
2. ¿Algo del contenido será público (perfiles, proyectos) o todo es interno?
3. ¿Cuántos usuarios se esperan en el piloto? Afecta poco con SQLite, pero conviene saberlo.
4. ¿Un co-responsable también puede aprobar propuestas? El plan asume que sí.
