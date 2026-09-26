# Portal de Investigación: diseño y estado

> **Contexto:** Instituto de Investigación Matemática (IIMAT) de la Carrera de Matemática (CMAT),
> Facultad de Ciencias Puras y Naturales (FCPN), Universidad Mayor de San Andrés (UMSA), La Paz,
> Bolivia. El portal sostiene la **acreditación de la Carrera y del Instituto ante IAC-CINDA**.
> Zona horaria America/La_Paz; montos en bolivianos (Bs). Ver la sección 13.

Documento de diseño del portal: qué hace, cómo está organizado, qué se decidió y qué queda
pendiente. Para instalarlo y trabajar en el código, vea el [README](README.md); para usarlo, la
[guía de uso](docs/guia-de-uso.md); para ponerlo en producción, la [guía de despliegue](docs/despliegue.md).

## 1. Visión

Portal interno donde cada investigador del instituto ingresa con su cuenta y mantiene al día su
actividad científica. Con esos mismos datos, sin volver a escribirlos, se generan el CV de cada
investigador, el informe de cada proyecto y la memoria anual del instituto.

Principio rector: **cada hecho se registra una sola vez**. Un artículo con tres autores del
instituto es *un* producto enlazado a tres personas, no tres registros. Un seminario de un
proyecto aparece a la vez en el proyecto y en el perfil de quien lo dictó.

## 2. Roles

| Rol | Cómo se obtiene | Qué puede hacer |
|---|---|---|
| **Administración** | Indicador `es_admin` de la cuenta | Crea cuentas (una a una, por CSV o con invitación), asigna la categoría de cada investigador(a), activa, desactiva, desbloquea y restablece; decide las propuestas institucionales y fija el plazo de cada convocatoria; ve todos los proyectos y reasigna su responsable (no los gestiona); ve la memoria anual, la auditoría y el CV de cualquier investigador |
| **Investigador(a)** | La cuenta tiene fila en `investigador`, con una categoría: titular, contratado(a), interino(a), invitado(a) o externo(a) | Edita su perfil; registra actividades y productos; crea proyectos individuales y participa en proyectos; genera su CV |
| **Responsable / co-responsable** | Rol dentro de un proyecto | Edita el proyecto y sus participantes; aprueba o rechaza propuestas; vincula registros directamente |
| **Participante** | Rol dentro de un proyecto (co-investigador, postdoc, tesista, colaborador) | Ve el proyecto; propone sus actividades y productos |
| **Persona externa** | Registro sin cuenta (`persona_externa`) | Figura como coautor, participante de actividades o de proyectos |

Una misma persona puede ser investigadora y administradora (p. ej., quien dirige el instituto).

## 3. Flujo de propuesta y aprobación

Las actividades y productos nacen en el espacio personal de quien los registra. En el formulario,
«Vincular a proyectos» ofrece los proyectos vigentes en que participa:

```
 Participante registra        Responsable del proyecto            Resultado
 ─────────────────────        ────────────────────────            ─────────
 actividad o producto ──propone──▶ bandeja «Pendientes» ──aprueba──▶ forma parte del proyecto
 (queda en su perfil)                                   ──rechaza──▶ vuelve con el motivo;
                                                                     sigue en su perfil
```

- Lo que vincula un **responsable** queda aprobado de inmediato.
- Al **aprobar** una actividad se puede asignar su responsable entre los participantes del proyecto.
- Al **rechazar**, el motivo es obligatorio. Quien propuso lo ve y, si guarda el registro con la
  casilla marcada, lo vuelve a proponer.
- Una propuesta **pendiente o rechazada** se retira desmarcando la casilla. Lo **aprobado** solo lo
  desvincula un responsable.
- Editar un registro ya aprobado no requiere nueva aprobación; el proyecto lo muestra en
  «Editados después de aprobados».
- Si un participante deja el proyecto, lo ya aprobado se conserva.
- Las fichas e informes del proyecto consideran solo lo aprobado.
- Hay avisos en la navegación (contador) y, opcionalmente, por correo.

## 4. Reglas de negocio

Se validan en el servidor; ocultar un botón nunca es la única protección.

**Productos**
- Nivel de revisión: `indexado`, `arbitrado` o `sin_arbitraje`. Los tipos sin revisión (reporte,
  preprint, presentación, software, tesis dirigida) quedan siempre `sin_arbitraje`.
- Un producto `indexado` debe figurar en al menos un índice con `cuenta_como_indexado = 1`.
- **Cuenta para el informe del instituto** si es indexado o arbitrado *y* está aceptado o
  publicado. En la memoria anual cada producto cuenta una vez, aunque tenga varios autores del
  instituto.
- DOI y arXiv son únicos: registrar uno existente ofrece «Sumarme como autor».
- Editan el creador y los autores del instituto; elimina solo el creador.

**Actividades**
- Fecha de término ≥ inicio; al menos un participante; editan el creador y los participantes del
  instituto; elimina el creador.

**Proyectos**
- Tipos: **individual** (lo crea cualquier investigador(a), que queda como responsable) e
  **institucional** (nace de una propuesta que acepta la administración; ver la sección 11).
- Siempre queda al menos un responsable vigente. El responsable no se cambia desde la pestaña
  de participantes: lo reasigna la administración. Las personas externas no pueden serlo.
- Gestionan el proyecto (datos, participantes, propuestas) solo sus responsables y
  co-responsables vigentes; la administración lo ve, pero no lo gestiona.
- Solo participantes vigentes proponen, y solo a proyectos no finalizados.
- El responsable de una actividad debe ser participante del mismo proyecto.
- Ven el proyecto sus participantes (actuales o anteriores) y la administración.
- Memoria: la producción de investigadores de categoría «Externo» figura solo si está aprobada
  en un proyecto institucional vigente en el periodo.

**Cuentas y acceso**
- Contraseñas con Argon2; mínimo 10 caracteres combinando letras con números o símbolos.
- Contraseña temporal → cambio obligatorio en el primer ingreso.
- 5 intentos fallidos en 15 minutos bloquean el ingreso (la administración puede desbloquear).
- Enlaces de recuperación e invitación de un solo uso (1 hora / 3 días); se guarda solo su hash.

## 5. Modelo de datos

Esquema vigente (migraciones `0001` a `0018` en `migrations/`):

```
usuario(id, email, nombres, apellidos, pass_hash, es_admin, activo, debe_cambiar_pass,
        creado_en, ultimo_acceso, avisos_correo)
investigador(usuario_id, grado, cargo, unidad, orcid, mr_id, zbmath_id, arxiv_id, scholar_url,
             pagina_web, bio, foto, perfil_publico, actualizado_en, categoria)
investigador_msc(usuario_id, codigo, principal, orden)
vinculo(id, usuario_id, categoria, fecha_inicio, fecha_fin, jornada_horas, nota, creado_por, creado_en)
msc(codigo, nivel, texto, texto_plano, descripcion)              -- MSC2020, 6.603 códigos
intento_login(id, email, ip, exito, fecha)
token_acceso(id, usuario_id, token_hash, proposito, expira_en, usado_en, creado_en)
auditoria(id, usuario_id, accion, entidad, entidad_id, detalle, fecha)

persona_externa(id, nombres, apellidos, institucion, pais, email, orcid, usuario_id, creado_por, creado_en)

tipo_actividad(id, nombre, orden, activo)
actividad(id, tipo_id, titulo, institucion, lugar, pais, fecha_inicio, fecha_fin, modalidad,
          ambito, url, descripcion, creado_por, creado_en, actualizado_en)
actividad_participante(actividad_id, orden, investigador_id | externo_id, rol)

tipo_producto(id, nombre, admite_revision, orden, activo)
indice(id, nombre, cuenta_como_indexado, cuenta_como_arbitrado, orden, activo)
revista(id, titulo, issn, eissn, pais, editorial, url, arbitrada, acceso_abierto, estado, nota,
        propuesta_por, verificada_por, verificada_en, creado_en, actualizado_en)
revista_indice(id, revista_id, indice_id, desde, hasta, cuartil, fuente, evidencia_url,
               verificado_por, verificado_en)
producto(id, tipo_id, titulo, anio, mes, revista_id, openalex_id, citas, citas_actualizadas, estado_publicacion, revision, medio, volumen, numero,
         paginas, doi, arxiv_id, url, resumen, actividad_id, creado_por, creado_en, actualizado_en)
producto_autor(producto_id, orden, investigador_id | externo_id, filiacion_instituto)
producto_indice(producto_id, indice_id)
adjunto(id, entidad, entidad_id, nombre, archivo, mime, tamano, subido_por, subido_en)

proyecto(id, codigo, nombre, descripcion, objetivo_general, fuente_financiamiento, monto,
         moneda, fecha_inicio, fecha_fin, estado, creado_por, creado_en, actualizado_en, tipo)
proyecto_objetivo(id, proyecto_id, orden, texto)
convocatoria(periodo, abre, cierra, actualizado_por, actualizado_en)
propuesta_institucional(id, proyecto_id, periodo, modalidad, nombre, descripcion, objetivo_general,
        metodologia, resultados_esperados, bibliografia, estado, proponente_id, creada_en,
        actualizada_en, enviada_en, envios, copia_enviada, decidida_por, decidida_en, comentario)
propuesta_objetivo(id, propuesta_id, orden, texto)
propuesta_actividad_prevista(id, propuesta_id, orden, descripcion, mes_previsto, actividad_id)
propuesta_evento(id, propuesta_id, accion, comentario, usuario_id, fecha)
aviso_enviado(clave, fecha)
proyecto_participante(id, proyecto_id, investigador_id | externo_id, rol, fecha_desde, fecha_hasta)
actividad_proyecto(actividad_id, proyecto_id, estado, responsable_participante_id,
                   propuesto_por, propuesto_en, revisado_por, revisado_en, comentario)
producto_proyecto(producto_id, proyecto_id, estado, propuesto_por, propuesto_en,
                  revisado_por, revisado_en, comentario, agradece)
```

`investigador_id | externo_id`: exactamente uno de los dos (restricción `CHECK`).

## 6. Arquitectura

- **FastHTML** (Starlette + componentes en Python) con **HTMX** para la interactividad y
  **MonsterUI** (FrankenUI + Tailwind) para los componentes.
- **SQLite** con **fastlite** y migraciones versionadas con **fastmigrate**. Una función
  `sin_tildes` registrada en SQLite permite buscar sin distinguir tildes ni mayúsculas.
- **KaTeX** en el navegador para las fórmulas de títulos y resúmenes.
- **Crossref** y **arXiv** para importar productos (`httpx2`); **bibtexparser** para BibTeX;
  **openpyxl** para XLSX; **Pillow** para las fotos; **argon2-cffi** para las contraseñas.
- Informes como páginas imprimibles; el PDF lo genera el navegador (ver decisiones).
- Estructura de módulos y convenciones de HTMX: ver el [README](README.md).

## 7. Estado por fase

| Fase | Contenido | Estado |
|---|---|---|
| 0. Base | Esqueleto, migraciones, datos de ejemplo, pruebas | ✔ |
| 1. Acceso | Login, bloqueo y desbloqueo, contraseña temporal, administración de cuentas, carga por CSV, páginas de error | ✔ |
| 2. Perfil | Edición en línea, identificadores, áreas MSC2020, foto, directorio interno | ✔ |
| 3. Actividades y productos | Registro con autores internos y externos, revisión e índices, duplicados, adjuntos, fichas | ✔ |
| 4. Proyectos | Participantes, objetivos, propuesta y aprobación, bandeja y contador de pendientes | ✔ |
| 5. Productividad | Importación desde DOI (Crossref) y arXiv; importar y exportar BibTeX | ✔ |
| 6. Informes | CV, informe de proyecto, memoria anual; descargas XLSX, CSV y BibTeX | ✔ |
| 7. Extras | Recuperación e invitación por correo, avisos, perfiles públicos, API JSON, auditoría | ✔ |

**Ajustes tras las pruebas con usuarios** (categorías, proyectos individuales e institucionales, propuestas anuales, informes por periodo): completos, ver la [sección 11](#11-ajustes-tras-las-pruebas-con-usuarios).

**Despliegue:** servidor propio (systemd + Caddy) o Fly.io (contenedor, volumen y réplica
continua de la base con Litestream). El paquete de datos (`scripts/paquete.py`) y el modo solo
lectura permiten mudarse entre ambos sin perder información.

340 pruebas automáticas. El detalle de cada entrega está en el historial de git (un commit por fase).

## 8. Decisiones tomadas

Las marcadas con **(confirmar)** las tomé durante el desarrollo por ser razonables, pero
conviene validarlas con el instituto antes del piloto.

- **Informe del instituto:** solo productos indexados o arbitrados. Si están enviados o en
  preparación, todavía no cuentan **(confirmar)**.
- **Qué índices cuentan como «indexado»:** WoS (SCIE y ESCI), Scopus, SciELO, MathSciNet y
  zbMATH sí; Latindex no **(confirmar)**.
- **Permisos sobre registros:** editan el creador y los coautores o participantes del instituto;
  elimina solo el creador **(confirmar)**.
- **Adjuntos** (certificados, etc.): solo los ven quienes pueden editar el registro y la administración.
- **Co-responsables** tienen los mismos permisos que el responsable, incluida la aprobación **(confirmar)**.
- **Proyectos** privados: los ven sus participantes y la administración **(confirmar)**.
- **Perfil público** desactivado por defecto; cada persona decide. No se publican correo,
  actividades, proyectos, adjuntos, trabajos en curso ni presentaciones.
- **PDF desde el navegador:** los generadores del lado del servidor (WeasyPrint, Typst) no
  entienden el LaTeX de títulos y resúmenes, y WeasyPrint exige librerías del sistema.
- **Importaciones:** los artículos importados de Crossref o BibTeX quedan como arbitrados (la
  fuente no dice si la revista está indexada). Los tipos sin equivalente, como `@phdthesis`, no
  se importan.
- **Cuentas nuevas:** por defecto con invitación por correo (cada persona define su
  contraseña); si no hay correo, con contraseña temporal.
- **Validación institucional** de registros (declarado → validado): no en el piloto.
- **Ingreso:** usuario y contraseña propios del portal; sin SSO ni LDAP en el piloto.

## 9. Pendiente

**Antes de producción** (ver [despliegue](docs/despliegue.md) o [Fly.io](docs/despliegue-fly.md)):
- Compilar Tailwind localmente en lugar de cargarlo desde un CDN (el aviso de la consola lo
  recomienda) y, idealmente, servir también los scripts de htmx, FrankenUI y KaTeX desde el propio servidor.
- Configurar SMTP, `PORTAL_URL`, `PORTAL_SECRET_KEY`, `PORTAL_HTTPS_ONLY=1` y `PORTAL_CONTACTO`.
- Revisar con el instituto las decisiones marcadas «(confirmar)».
- Elegir dónde alojar el piloto (servidor del instituto o Fly.io) según su política sobre datos
  personales en proveedores externos; usar un dominio propio desde el inicio facilita mudarse.
- Si se usa Fly.io: probar un despliegue real. La imagen se construyó y se probó localmente con
  Podman (arranque con Litestream, paquete de datos y restauración tras destruir el volumen);
  falta probarla en la plataforma, con Tigris como réplica.

**Funcionalidad que el plan original incluía y aún no está:**
- Administrar los catálogos (tipos de actividad y de producto, índices) desde la interfaz. Hoy
  se cambian con una migración.
- Fusionar personas externas duplicadas, y vincular una persona externa a su cuenta si luego la recibe.
- Áreas MSC en los productos (hoy solo en los perfiles).
- Enlace formal entre un preprint y su versión publicada, como registros separados. Hoy la
  versión publicada importada conserva el arXiv en el mismo registro.

**Futuro, si se requiere:** validación institucional, SSO o LDAP, integración con el
repositorio institucional, proyectos públicos, cuartiles o factor de impacto de las revistas.

## 10. Preguntas abiertas

1. ¿La agencia financiadora exige cuartiles (Q1–Q4) o factor de impacto de las revistas indexadas?
2. ¿Cuántas personas participarán en el piloto? Con SQLite no cambia mucho, pero ayuda a
   dimensionar el servidor y los respaldos.
3. ¿El instituto quiere publicar los proyectos, además de los perfiles?
4. ¿Hace falta registrar la tesis doctoral propia (hoy no hay un tipo de producto para eso)?

## 11. Ajustes tras las pruebas con usuarios

Cambios pedidos por el instituto después de las primeras pruebas (septiembre de 2026). Se
implementan por etapas; cada una termina con pruebas, datos de ejemplo y documentación al día.

### Lo que pidió el instituto

1. **Dos tipos de proyecto.** Los **individuales** se registran sin aprobación. Los
   **institucionales** se proponen y pasan por revisión; la administración los acepta, los acepta
   con condiciones o los rechaza. Además de los datos básicos, una propuesta institucional incluye
   metodología, resultados esperados, actividades previstas y bibliografía. Sobre los proyectos
   institucionales, la administración solo decide su aceptación.
2. **Periodo anual.** Un proyecto institucional rige de octubre a septiembre (p. ej. oct/2026 –
   sept/2027). Las propuestas se presentan durante septiembre y pueden ser de **continuidad** o de
   un **proyecto nuevo**. Si el responsable no propone continuidad (ni un proyecto nuevo), el
   proyecto concluye en septiembre. Quien propone queda como responsable.
3. **Categorías de investigador:** Titular, Contratado(a), Interino(a), Invitado(a) y Externo(a).

### Respuestas del instituto a las preguntas del plan

| Tema | Respuesta |
|---|---|
| Categorías | Son cinco; la cuarta es «Invitado(a)». |
| Categoría y permisos | Solo titulares y contratados proponen proyectos institucionales o son responsables; los interinos pueden ser co-responsables. |
| Externos en la memoria | Figuran en la memoria del instituto si están ligados a un proyecto institucional. |
| Aceptación condicional | El proyecto **queda en espera** hasta que el responsable corrija y la administración acepte. |
| «Administrador principal» | Es la misma administración de siempre (no hay un rol aparte). |
| Proyectos existentes | Pasan todos a individuales. En los datos de ejemplo, el FONDECYT queda como institucional. |
| Propuesta de continuidad | Repite todas las secciones, precargadas desde el periodo anterior y editables (nuevos objetivos, nuevo plan de actividades). |
| Memoria | Además del año calendario, por periodo de vigencia (octubre–septiembre) y por un rango de fechas que elija quien la genera. |

### Interpretaciones propias (confirmar)

- Las restricciones por categoría se aplican a los proyectos **institucionales**. Un proyecto
  individual lo puede registrar cualquier investigador(a) y queda como responsable **(confirmar)**.
- «Ligado a un proyecto institucional» significa que el producto o actividad está **aprobado** en
  un proyecto institucional vigente en el periodo del informe **(confirmar)**.
- La categoría la asigna y cambia solo la administración. No se guarda su historial: los informes
  de años anteriores usan la categoría actual **(confirmar)**.
- Una continuidad enviada que aún no se decide al 1 de octubre mantiene el proyecto vigente
  («en renovación») hasta la decisión; si se rechaza, el proyecto concluye el 30 de septiembre.
- Los borradores se preparan en cualquier momento; solo se **envían** dentro del plazo. La
  administración puede ampliar o reabrir el plazo de una convocatoria.

### Diseño

**Categorías.** Columna `investigador.categoria` (`titular`, `contratado`, `interino`,
`invitado`, `externo`; vacía = «sin categoría», que la administración debe completar). Se asigna
al crear la cuenta, en la carga por CSV y desde el listado de usuarios. Se ve en el perfil, el
directorio (con filtro) y la memoria.

**Tipo de proyecto.** Columna `proyecto.tipo` (`individual` | `institucional`).

- *Individual:* cualquier investigador(a) lo crea desde «Proyectos» y queda como responsable.
  Participantes, propuestas de actividades y productos y su aprobación siguen como hoy.
- *Institucional:* nace de una propuesta. La administración deja de crear proyectos y de asignar
  responsables en el uso normal; conserva la posibilidad de reasignar al responsable (p. ej., si
  alguien deja el instituto).

**Propuestas institucionales.**

```
propuesta_institucional(id, proyecto_id, periodo, modalidad, metodologia, resultados_esperados,
        bibliografia, estado, proponente_id, enviada_en, copia_enviada, decidida_por, decidida_en,
        comentario, UNIQUE (proyecto_id, periodo))
    periodo:   año de inicio (2026 = 1-oct-2026 a 30-sep-2027)
    modalidad: nuevo | continuidad
    estado:    borrador | enviada | aceptada | condicional | rechazada | retirada
propuesta_actividad_prevista(id, propuesta_id, orden, descripcion, mes_previsto)
convocatoria(periodo, abre, cierra)          -- por omisión, del 1 al 30 de septiembre
```

```
borrador ──enviar──▶ enviada ──▶ aceptada ─────────▶ proyecto vigente en el periodo
  ▲                    │   └──▶ rechazada (motivo)
  │                    └──────▶ condicional (condiciones) ──responsable corrige y reenvía──┐
  └────────────────────────────────────────────────────────────────────────────────────────┘
```

- Al enviar se congela una copia (`copia_enviada`) de lo que revisa la administración.
- *Nuevo:* crea el proyecto en estado «En formulación». *Continuidad:* solo la presenta un
  responsable del proyecto, con todas las secciones precargadas del periodo anterior.
- Proponer y ser responsable: titulares y contratados. Co-responsable: también interinos.
- Vigencia: un proyecto institucional está vigente mientras una propuesta aceptada cubra la fecha
  (o haya una continuidad enviada sin decidir). Se calcula por fechas, sin tareas programadas.
- Bandeja «Propuestas institucionales» para la administración, por periodo, con contador en la
  navegación. Avisos: a la administración al recibir una propuesta, al proponente con la decisión,
  y a los responsables en septiembre si su proyecto termina y no han propuesto continuidad.

**Memoria.** Periodo elegible: año calendario, periodo oct–sep o rango libre de fechas. Cuentan
los productos con al menos un autor del instituto de categoría distinta de «Externo», o bien
ligados a un proyecto institucional. Desglose por categoría y columna de categoría en «Por investigador».

### Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| A | Categorías: migración, cuentas (alta, CSV, cambio desde el listado), perfil, directorio con filtro, memoria | ✔ |
| B | Tipo de proyecto: individuales creados por investigadores, ajuste de permisos de la administración, listados; regla de externos en la memoria | ✔ |
| C | Propuestas institucionales: formulario, borrador y envío, convocatoria y plazos, bandeja de decisión, condiciones, continuidad, vigencia automática, avisos | ✔ |
| D | Informes: memoria por periodo oct–sep y por rango; exportar las propuestas de una convocatoria (XLSX); actividades previstas frente a realizadas | ✔ |

**Detalles de la etapa C:**

- Una propuesta nueva crea el proyecto «En formulación» y su responsable es quien propone. Si el
  borrador se elimina y el proyecto no tiene otra historia, se elimina también.
- La propuesta guarda su propio contenido (nombre, descripción, objetivos, etc.). Al aceptarse,
  los datos básicos y los objetivos pasan al proyecto; en un proyecto institucional no se editan
  directamente (sí el código, el financiamiento y el monto).
- Al enviar se congela una copia (`copia_enviada`): si la propuesta queda condicional y se está
  corrigiendo, la administración sigue viendo la última versión enviada.
- Una propuesta rechazada de un proyecto nuevo deja el proyecto en formulación (se puede volver a
  proponer en otra convocatoria).
- La vigencia se recalcula al arrancar, a lo más una vez por hora (Beforeware) y tras cada
  decisión. Los recordatorios de continuidad se envían una vez por proyecto y periodo.
- Datos de ejemplo: el FONDECYT 1260001 (Emmy) aceptado para 2025–2026 (termina el 30 de
  septiembre) y una propuesta nueva de Sofía por decidir.

**Detalles de la etapa D:**

- Los productos solo tenían año. Se agregó el **mes de publicación** (opcional; se toma de
  Crossref, arXiv y BibTeX al importar). En un periodo o rango, un producto con mes se ubica por
  su mes; uno sin mes cuenta si todo su año cae dentro, y si cae solo en parte queda **«por
  confirmar»** (se lista, no se cuenta). Las actividades se ubican por su fecha de inicio.
- Plan: cada actividad prevista de una propuesta aceptada puede enlazarse con la actividad
  registrada que la cumple (aprobada en el proyecto y del mismo periodo). Estados: pendiente,
  atrasada, realizada. Aparece en la pestaña «Plan» y en el informe de proyecto (HTML y XLSX).
- XLSX de una convocatoria: hojas Propuestas, Textos, Objetivos y Actividades previstas, con la
  copia enviada de cada propuesta (sin borradores).

Nota: la convocatoria de septiembre de 2026 cierra el 30; lo realista es que el piloto use la
de septiembre de 2027, o que la administración abra un plazo extraordinario.

## 12. Filiación y periodo de pertenencia

Para que las cifras institucionales resistan una revisión externa, un producto o actividad cuenta
para el instituto solo si **al menos un autor o participante del instituto**:

1. tenía **vínculo vigente** con el instituto en la fecha del producto (año y mes de publicación)
   o de la actividad (fecha de inicio), y
2. en productos, **firmó con la filiación del instituto**.

La producción anterior al ingreso se registra en el perfil y el CV, pero no cuenta en los informes
institucionales.

### Respuestas del instituto

| Tema | Respuesta |
|---|---|
| Institución | El Instituto de Investigación Matemática (IIMAT) es parte de la Carrera de Matemática (CMAT), de la Facultad de Ciencias Puras y Naturales (FCPN) de la Universidad Mayor de San Andrés (UMSA), Bolivia. |
| Qué filiación vale | IIMAT o cualquiera de las instancias que lo contienen, incluida la UMSA. Vale la doble filiación. |
| Producción anterior al ingreso | Se registra en el perfil, pero no cuenta en los informes institucionales. Cuenta si hay vínculo en la fecha **y** filiación. |
| Invitados y externos | Como ahora: los externos figuran si están ligados a un proyecto institucional. |
| Desactivar una cuenta | El portal pregunta si también termina el vínculo y en qué fecha. |
| Datos históricos | Los tiene Recursos Humanos; hay varios periodos por persona (ingreso y cambios de categoría). |
| Informes de proyecto | Los fondos exigen filiación **y** que la publicación agradezca al proyecto. |

### Diseño

- `vinculo(id, usuario_id, categoria, fecha_inicio, fecha_fin, jornada_horas, nota, …)`:
  periodos sin superposición. `fecha_inicio` vacía = ingreso desconocido (se trata como «desde
  siempre» y los informes lo advierten). `jornada_horas` queda lista para indicadores por jornada.
  `investigador.categoria` pasa a ser la categoría del vínculo vigente (se recalcula sola).
- Los informes usan la **categoría a la fecha** de cada producto o actividad.
- Un producto sin mes cuyo año solo en parte cae dentro del vínculo del autor queda «por
  confirmar», como en la memoria por periodo.
- `producto_autor.filiacion_instituto` (sí / no / sin declarar), con detección al importar según
  los nombres del instituto (IIMAT, CMAT, FCPN, UMSA y sus nombres completos).
- `producto_proyecto.agradece` (sí / no / sin declarar): la publicación agradece al proyecto.

**Detalles de E1:**

- Las cuentas que ya tenían categoría recibieron un periodo vigente sin fecha de ingreso. La
  memoria advierte quiénes no tienen fecha de ingreso y quiénes no tienen vínculo registrado (su
  producción no cuenta).
- En la memoria, el resumen por investigador incluye a quienes estuvieron vinculados en el periodo
  aunque ya no lo estén (con «hasta …»), con su categoría al final del periodo. El desglose por
  categoría cuenta cada registro con la categoría de sus autores a la fecha.
- La carga de cuentas por CSV acepta además `fecha_ingreso`.
- Pendiente de decidir: el cálculo por jornada (punto 3 del análisis) ya tiene el dato.

### Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| E1 | Historial de vínculo: migración, ventana «Vínculo» en la administración, carga del historial por CSV (reemplaza el de cada persona del archivo), pregunta al desactivar, perfil, reglas de vínculo y categoría a la fecha en la memoria | ✔ |
| E2 | Filiación: casilla por autor, detección al importar, filtro y confirmación masiva, «por confirmar» en la memoria | ✔ |
| E3 | Agradecimiento al proyecto, informe de proyecto con filiación y agradecimiento, datos de ejemplo y documentación | ✔ |

**Detalles de E2:**

- Selector por autor del instituto en el formulario («Firmó con IIMAT/UMSA», «Sin filiación del
  instituto», «Sin declarar»); los externos llevan un campo oculto para mantener las listas en paralelo.
- Al importar por DOI se marca «Firmó» si la afiliación publicada menciona IIMAT, CMAT, FCPN o
  UMSA (o sus nombres completos; `PORTAL_FILIACIONES`). BibTeX no trae afiliaciones.
- Solo se pide declarar la filiación en productos indexados o arbitrados (los únicos que cuentan).
  Aviso en el inicio, filtro «Sin filiación declarada», botones Sí / No y declaración masiva.
- Memoria: cuenta si al menos un autor vinculado en la fecha firmó con la filiación. «Por
  confirmar» indica el motivo (sin mes, vínculo parcial, filiación sin declarar). El CV admite
  «solo con filiación IIMAT/UMSA».

**Detalles de E3:**

- `producto_proyecto.agradece` (sí / no / sin declarar): se indica en el formulario del producto
  (junto a cada proyecto), al aprobar la propuesta y en la pestaña Productos (responsables).
- Informe de proyecto: cuántos productos que cuentan cumplen filiación **y** agradecimiento, y
  qué le falta a cada uno; columnas nuevas en el XLSX. La filiación del producto es «sí» si algún
  autor del instituto firmó con ella.

## 13. Contexto boliviano y acreditación IAC-CINDA

- **Ajustes hechos:** zona horaria America/La_Paz para «hoy», plazos, vigencias y horas mostradas
  (la base sigue guardando UTC; la imagen instala `tzdata`); montos en bolivianos (Bs); ejemplos
  de proyectos con recursos IDH de la UMSA y del International Science Programme (ISP); dominios de
  ejemplo en `umsa.bo`.
- **Corrección:** el análisis de brechas anterior citaba normativa chilena (ANID, CNA, Ley 21.719)
  por un supuesto erróneo sobre el país; no aplica. Las exigencias de protección de datos y de
  reporte deben revisarse con la normativa boliviana y de la UMSA.
- **IAC-CINDA:** la acreditación de la Carrera y del Instituto se hará con el Instituto
  Internacional para el Aseguramiento de la Calidad (IAC) de CINDA. Pendiente: conseguir su guía o
  manual de criterios vigente y hacer una tabla de correspondencia criterio → dato del portal →
  evidencia, para detectar lo que falta registrar y preparar un «informe para acreditación»
  (indicadores del periodo evaluado, normalmente varios años, con sus evidencias).

## 14. Catálogo de revistas: indexación verificada por año

Hoy cada autor declara si su artículo es indexado y en qué índices. Eso produce inconsistencias
(la misma revista indexada para uno y no para otro) y no resiste una revisión externa. Además, la
indexación de una revista cambia con los años. IAC-CINDA (criterio 3.6.3) pide evidencia de los
últimos 5 años de «publicaciones científicas en revistas indexadas tanto nacionales como
internacionales», que el programa «exprese de manera abierta y transparente los datos, métodos y
métricas» y que promueva la ciencia abierta.

### Diseño

- `revista(id, titulo, issn, eissn, pais, editorial, url, arbitrada, acceso_abierto, estado,
  nota, propuesta_por, verificada_por, verificada_en, …)`. `estado`: `verificada` (la revisó la
  administración) o `pendiente` (la propuso un investigador o se creó al importar).
- `revista_indice(revista_id, indice_id, desde, hasta, cuartil, fuente, evidencia_url,
  verificado_por, verificado_en)`: la revista figura en ese índice entre esos años (hasta vacío =
  vigente), con la fuente consultada (p. ej., «Lista maestra de Scopus, junio 2026») y un enlace
  de evidencia. Cuartil opcional (Q1–Q4), por si se requiere.
- `producto.revista_id`: los artículos en revista eligen la revista del catálogo (autocompletar
  por título o ISSN; al importar por DOI, se reconoce por el ISSN que trae Crossref).
- **Revisión e índices derivados:** si la revista está verificada, el nivel de revisión y los
  índices del artículo se calculan del catálogo **según el año de publicación** y no se editan a
  mano. Sin revista verificada, rige lo declarado, marcado como «declarado, sin verificar».
- Nacional o internacional según el país de la revista (Bolivia = nacional). Acceso abierto
  para el indicador de ciencia abierta.
- La administración mantiene el catálogo: alta y edición, periodos de indexación con su fuente,
  verificación de revistas propuestas, carga por CSV (solo las revistas donde publica el
  instituto; no hace falta cargar listas completas) y una lista de artículos sin revista del
  catálogo, agrupados por el nombre declarado, para vincularlos.

### Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| R1 | Catálogo: tablas, validación de ISSN, administración (lista, ficha, indexaciones con fuente y evidencia, verificación), carga por CSV | ✔ |
| R2 | Productos: selector de revista, propuesta de revista nueva, reconocimiento por ISSN al importar, derivación de revisión e índices por año, vinculación de artículos existentes | ✔ |
| R3 | Informes: origen del dato (catálogo o declarado), revistas nacionales e internacionales, acceso abierto, cuartiles; fuente y fecha de verificación en las exportaciones | ✔ |

**Detalles de R2:**

- Al guardar un artículo con revista verificada, la revisión y los índices se toman del catálogo
  (año de publicación) y el medio pasa a ser el título de la revista. Cualquier cambio del catálogo
  (verificar, editar, indexaciones, carga por CSV, vinculación) reclasifica sus artículos.
- Propuesta de revista desde el formulario (queda pendiente, con quien la propuso); si su ISSN o
  título ya existen, se reutiliza la revista. Crossref: reconocimiento por ISSN o título; si no
  está, se ofrece proponerla. BibTeX: reconocimiento por ISSN o título (sin crear revistas) y el
  ISSN se exporta.
- Administración: «Artículos sin revista», agrupados por el nombre declarado, con sugerencia por
  título, para vincular o crear la revista.
- Tipos nuevos (migración 0016, IAC-CINDA 3.6.3): productos «Patente» y «Traducción»; actividades
  «Transferencia de conocimiento», «Participación en red de investigación» y «Estancia o pasantía
  de investigación» (renombra «Estadía de investigación»). El CV los agrupa y la memoria informa
  patentes y traducciones aparte.

### Decisiones del instituto

1. Artículos en revistas **sin verificar**: cuentan durante el piloto (marcados como declarados);
   al preparar la acreditación se exigirá revista verificada.
2. El catálogo lo mantiene la administración durante el piloto.
3. SciELO queda como un solo índice (sin separar SciELO Bolivia). **Latindex Catálogo cuenta como
   arbitrado** (no como indexado): una revista que figura en él clasifica sus artículos como
   arbitrados aunque no declare revisión por pares (`indice.cuenta_como_arbitrado`, migración 0017).

**Detalles de R3:**

- Memoria: sección «Revistas de los artículos» (nacionales / internacionales según el país de la
  revista, acceso abierto, mejor cuartil del año, clasificados por el catálogo o declarados) y
  sección final «Datos y método» con las reglas y la política de índices (IAC-CINDA 3.6.3).
- Exportaciones de productos (memoria, informe de proyecto, CSV): mes, revista del catálogo, ISSN,
  país, ámbito, acceso abierto, mejor cuartil, origen de la clasificación y fuente de cada
  indexación con su fecha de verificación.
- `PORTAL_EXIGIR_REVISTA_VERIFICADA=1` (para la acreditación): los artículos en revistas no
  verificadas quedan «por confirmar».

### Por confirmar con el instituto

1. (Resuelto: ver «Decisiones del instituto».)
2. (Resuelto: ver «Decisiones del instituto», punto 3.)
3. (Resuelto: la administración, durante el piloto.)

## 15. Correspondencia con IAC-CINDA

Tabla completa (criterio → qué registra el portal → brecha, con estado): 
https://claude.ai/artifact/VuTd7X3jxFy3Fx4JgwH4wU (privada; compartir desde el menú de la página).

- Base: criterios de pregrado de IAC-CINDA (junio 2025, v1.2), que aplican a la Carrera de
  Matemática. **Pendiente:** confirmar con IAC-CINDA qué conjunto de criterios corresponde al
  Instituto (el Modelo 2025 describe procesos para instituciones, carreras, maestrías y doctorados).
- De 33 criterios revisados que tocan la investigación: 11 cubiertos, 18 parciales, 4 brechas; 12
  más dependen de políticas o procesos fuera del portal.

**Prioridades para el portal** (por aporte a la acreditación):

1. Carga automática desde ORCID u OpenAlex, con citas (3.6.1, 3.6.3) — ✔ (ver sección 16).
2. Anexo de I+D+i para la acreditación: informe de 5 años ordenado por criterio, con evidencias (4.3.1).
3. Estudiantes en la investigación: tesistas y estudiantes en tesis, proyectos y publicaciones (2.3.2, 3.6.1 d).
4. Internacionalización: ámbito de los proyectos e indicador de coautoría internacional (3.5.2 c, 3.6.3 h).
5. Líneas prioritarias de investigación y su asignación (3.1.1, 3.6.1 a).
6. Indicadores normalizados: jornada completa equivalente y conteo fraccionado (2.2.1, 2.2.2).
7. Premios y distinciones, arbitraje de artículos, asesorías y prestación de servicios, impacto de
   la vinculación (2.2.1 d, 3.4.1, 3.4.3).
8. Datos de diversidad (género, edad), solo si el instituto lo decide y con consentimiento (2.2.1 c).

## 16. Carga automática desde OpenAlex y citas

- **Fuente:** OpenAlex (abierto y gratuito), consultado por el ORCID del perfil. Se eligió frente a
  la API pública de ORCID porque trae coautores con sus afiliaciones (sirve para detectar la
  filiación IIMAT/UMSA), revista con ISSN, acceso abierto y citas. OpenAlex contabiliza el uso por
  consulta; `PORTAL_OPENALEX_CLAVE` permite usar una clave si el cupo gratuito no alcanzara.
- **Flujo:** «Mis productos → Buscar en OpenAlex» (últimos 5 años por omisión, hasta 200 obras por
  búsqueda). Cada obra se clasifica como nueva, ya registrada (por id de OpenAlex, DOI, arXiv o
  título y año), descartada o que no se importa (tesis propia, datos, erratas…). El investigador
  elige qué registrar; nada entra sin su confirmación.
- **Al registrar:** tipo según OpenAlex y su fuente; autores reconocidos por ORCID o nombre (el
  investigador, siempre por su ORCID); revista del catálogo por ISSN o título, o propuesta como
  pendiente; filiación marcada si la afiliación publicada menciona al instituto; citas y fecha.
- **Descartar:** oculta una obra en las búsquedas siguientes (`cosecha_descartada`).
- **Citas:** «Actualizar citas» (administración, en la memoria) consulta todos los productos con
  DOI. La memoria tiene una sección «Impacto»; los XLSX, las citas por producto con su fecha.
- **Calidad de los datos:** OpenAlex atribuye a veces obras ajenas. Un ORCID de relleno (el de
  prueba 0000-0002-1825-0097, que usa un investigador de los datos de ejemplo) devuelve más de mil
  obras de otras personas: el portal lo advierte cuando hay más de 40 obras por año.
- **Pendiente:** búsqueda para quienes no tienen ORCID (por nombre y afiliación en OpenAlex, con
  más riesgo de errores); actualización periódica de citas sin intervención.
