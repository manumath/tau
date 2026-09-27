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

Esquema vigente (migraciones `0001` a `0020` en `migrations/`):

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
estudiante(id, externo_id, nivel, programa, del_programa, desde, hasta, titulado, registrado_por, creado_en)

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
         moneda, fecha_inicio, fecha_fin, estado, creado_por, creado_en, actualizado_en, tipo, ambito)
proyecto_objetivo(id, proyecto_id, orden, texto)
proyecto_contraparte(id, proyecto_id, institucion, pais, creado_en)
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

382 pruebas automáticas. El detalle de cada entrega está en el historial de git (un commit por fase).

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
- De 33 criterios revisados que tocan la investigación: 15 cubiertos, 16 parciales, 2 brechas; 12
  más dependen de políticas o procesos fuera del portal.

**Prioridades para el portal** (por aporte a la acreditación):

1. Carga automática desde ORCID u OpenAlex, con citas (3.6.1, 3.6.3) — ✔ (ver sección 16).
2. Anexo de I+D+i para la acreditación: informe de 5 años ordenado por criterio, con evidencias (4.3.1) — ✔ (sección 17).
3. Estudiantes en la investigación: tesistas y estudiantes en tesis, proyectos y publicaciones (2.3.2, 3.6.1 d) — ✔ (sección 18).
4. Internacionalización: ámbito de los proyectos e indicador de coautoría internacional (3.5.2 c, 3.6.3 h) — ✔ (sección 19).
5. Líneas prioritarias de investigación y su asignación (3.1.1, 3.6.1 a) — ✔ (sección 21).
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

## 17. Anexo de I+D+i para la acreditación

«Informes → Anexo de I+D+i para la acreditación» (administración): documento imprimible y XLSX
para la ventana de años elegida (por omisión los últimos 5; hasta 11 años), con las reglas de la
memoria (vínculo en la fecha, filiación, catálogo de revistas).

- **Resumen por año:** investigadores y JCE, artículos indexados y arbitrados, revistas nacionales e
  internacionales, libros y capítulos, patentes/software/traducciones, presentaciones, estancias,
  transferencia, redes, proyectos vigentes y citas.
- **Por criterio:** 2.2.1 cuerpo académico (categoría al 31 de diciembre; JCE = horas/40), 3.6.3 a–j,
  2.2.1 d comités, 3.5.2 c coautoría internacional (preliminar: depende del país de los coautores
  externos), 3.6.1 impacto; lista de lo que el portal aún no registra; «Datos y método».
- **Revistas:** por omisión solo cuentan artículos en revistas verificadas (lo que corresponde a la
  acreditación); la opción «Incluir revistas sin verificar» sirve durante el piloto.
- **Presentaciones (3.6.3 i):** eventos científicos con al menos un expositor del instituto.
- La ventana usa años completos: un producto del año en curso sin mes cuenta; el cuerpo académico
  del año en curso se mira a la fecha de hoy.

## 18. Estudiantes en la investigación

- Los estudiantes y tesistas son personas externas con **periodos de estudio** (`estudiante`):
  nivel (licenciatura, maestría, doctorado), programa, si es del programa propio (Matemática, UMSA),
  años de ingreso y egreso, y titulación. Una persona era estudiante un año si cae en un periodo; es
  graduada si egresó titulada antes de ese año. Puede tener varios periodos (licenciatura y luego
  maestría).
- **Página «Estudiantes y tesistas»** (desde Investigadores): lista con filtros por nivel y estado,
  alta (eligiendo una persona externa existente o creándola), ficha con periodos y participación
  (tesis, productos, proyectos, actividades). La registran investigadores y administración.
- **Tesis dirigidas:** producto «Tesis dirigida» con el tesista entre los autores; los autores del
  instituto son quienes dirigen (deben estar vinculados en la fecha). En curso = «en preparación»;
  defendida = «publicado». El CV las agrupa.
- **Anexo de acreditación:** sección «Estudiantes en la investigación» (2.3.2 · 3.6.1 d · 2.3.4):
  tesis por nivel y estado, productos con estudiantes coautores, productos con graduados, proyectos y
  actividades con estudiantes; filas en el resumen por año y hojas en el XLSX.
- El selector de autores y participantes muestra «Estudiante de …» o «Graduado(a) de …».

## 19. Internacionalización

- **País de las personas externas**, normalizado (`app/comun/paises.py`: «USA», «EE. UU.» → «Estados
  Unidos»): desde OpenAlex (código de país de las instituciones del autor), deducido del texto de
  la afiliación al importar por DOI («…, Oxford, UK» → «Reino Unido») o de la institución al crear
  la persona. Nunca se sobrescribe un país ya registrado.
- **Página «Coautores externos»** (desde Investigadores): lista las personas sin país primero, para
  completar institución y país; «Completar países automáticamente» normaliza y deduce.
- **Proyectos:** ámbito nacional o internacional (también editable en los institucionales) e
  instituciones contraparte con país. Sin ámbito declarado, se deduce de las contrapartes.
- **Anexo de acreditación (3.5.2 c):** artículos con coautoría internacional, cobertura (en cuántos
  se conoce el país de todos los coautores externos, con aviso si falta), países de los coautores,
  proyectos internacionales con sus contrapartes y estancias internacionales; filas nuevas en el
  resumen por año y hoja de países en el XLSX. El informe de proyectos exporta ámbito y contrapartes.

## 20. Protección CSRF

La cookie de sesión es `SameSite=Lax`: protege de formularios de *otros sitios*, pero no de otros
subdominios del mismo sitio (en un dominio universitario, cualquier página en `*.umsa.bo`). Desde
el 26 de septiembre de 2026, toda petición que modifica datos debe venir del propio portal según
`Origin` (o `Referer`, si falta): el host de la petición, `PORTAL_URL` o `PORTAL_ORIGENES_EXTRA`.
Es la verificación de origen que recomienda OWASP; no requiere tokens ni cambiar formularios. Sin
`Origin` ni `Referer` se admite (no es un navegador con la sesión de otra persona).

Verificado con el servidor de desarrollo: un origen del propio portal se acepta (200) y uno de otro
subdominio se rechaza (403).

## 21. Líneas de investigación institucionales

La Guía de Antecedentes de IAC-CINDA pide la línea de investigación en proyectos, desarrollo
académico, publicaciones, libros y patentes (hojas 19–23 y 25), y su hoja 2 fija las seis líneas del
programa: Sistemas Dinámicos, Estructuras Algebraicas Ordenadas, Teoría de Control, Modelos
Matemáticos y Computación, Optimización Matemática y Áreas Fundamentales Complementarias (cargadas
por la migración 0021).

- **Las líneas cambian:** cada una tiene vigencia (`vigente_desde`, vacío = desde antes del portal;
  `vigente_hasta`, vacío = sigue vigente). Una línea que deja de regir no se borra: se le pone fecha
  de término y quien ya la usaba la conserva en su historia. Solo se elimina una línea sin uso.
  Corregir la redacción se hace editándola; reformularla o dividirla, cerrándola y creando las nuevas.
- **Catálogo:** lo mantiene la administración (menú con su nombre → «Líneas de investigación»):
  alta, edición, vigencia, orden y ficha con los proyectos e investigadores de cada línea.
- **Propuestas institucionales:** al formularla se eligen **explícitamente** las líneas vigentes al
  inicio del periodo (1 de octubre); al menos una para enviarla. Si una línea elegida deja de regir
  antes del envío, queda marcada y hay que quitarla. Al aceptarse, sus líneas pasan al proyecto; en
  un proyecto institucional con propuesta aceptada no se editan (cambian en la continuidad, que
  las precarga si siguen vigentes). La copia enviada y el XLSX de la convocatoria las incluyen.
- **Proyectos individuales:** adscripción opcional desde el resumen, a líneas vigentes hoy.
- **Investigadores:** adscripción opcional desde «Mi perfil», a líneas vigentes. Se muestra en su
  perfil interno y en el público (solo las vigentes; también en la API).
- **Productos y actividades** (hojas 19, 22, 23 y 25) no eligen línea: la heredan de los proyectos
  en que están **aprobados** (sin repetir; lo pendiente o rechazado no cuenta). Sin proyecto
  aprobado no tienen línea. Se ve en su ficha y en los XLSX de la memoria (también en proyectos).


## 22. Ampliación a gestión curricular y docente (opción 2)

Evaluación y opciones: https://claude.ai/artifact/SqsBxjJsvWFUC6QyNViebV (privada). Se elige un
solo sistema organizado en módulos (Investigación, Docencia y Currículo, Acreditación) con el
mismo stack. **Fuera de alcance:** registro académico (inscripciones, notas, kárdex, actas); esos
datos se importan agregados del sistema académico de la UMSA.

Las estimaciones suponen una persona a medio tiempo con asistencia de IA; son orientativas.

### Fase 0 — Decisiones (1–2 semanas, sin código)

- ¿Quién mantiene el sistema tras el piloto? Reunión con el área de TI de la UMSA (DTIC): si exige
  PostgreSQL o un framework estándar, se decide aquí migrar (opciones 4 o 5) y la fase 1 cambia.
- Alcance académico con la Dirección de Carrera: qué hojas de la Guía se llenarán desde el sistema.
- Qué entrega el sistema académico de la UMSA (formato, periodicidad, nivel de agregación).
- «Jerarquía académica» de la hoja 10: ¿categoría del portal o escalafón docente?
- Fecha de nacimiento (tramos de edad, hoja 11): decisión explícita y aviso a los académicos.
- Nombre del sistema. Una segunda persona que acompañe desde la fase 1 (continuidad).

**Decidido (26 de septiembre de 2026):**

- Mantienen el sistema la Dirección del IIMAT y personal de TI propio (no la DTIC, aunque
  coordinan con ella). La DTIC no impone software: **se conserva el stack** (FastHTML + HTMX,
  SQLite) y la fase 1 va completa.
- La Dirección de Carrera participa en la gestión del sistema junto con la Dirección del IIMAT y
  el personal de TI: la gobernanza es compartida (roles de ambas direcciones en la fase 2).
- Fecha de nacimiento: se registra, con aviso a los académicos, y **solo la ve la
  administración**. Los informes usan tramos de edad, nunca la fecha. Va en la persona académica
  (fase 2).
- Una segunda persona acompaña la implementación desde la fase 1.

**Pendiente de la fase 0:** qué datos entrega el sistema académico de la UMSA (condiciona la
fase 4), la «jerarquía académica» de la hoja 10 y el nombre del sistema. No bloquean las fases 1 a 3.

### Fase 1 — Saneamiento sin cambios visibles (3–4 semanas)

1. Paquetes: `app/comun` (db, auth, config, seguridad, correo, auditoría, componentes),
   `app/investigacion`, `app/acreditacion`, `app/academico` (vacío). Un commit por paquete; las
   pruebas pasan sin cambios de comportamiento.
2. Partir `routes/proyectos.py` (1.094 líneas) y `routes/productos.py` (890) por pestaña o flujo.
3. Aislar lo propio de SQLite (`date('now','localtime')`, `sin_tildes`, apsw) en `comun/db` para
   que una migración a PostgreSQL toque un solo lugar. Sin ORM.
4. Estilos servidos desde `/static` (Tailwind compilado y recursos de MonsterUI), sin CDN; luego
   una Content-Security-Policy estricta.
5. Pruebas en navegador (Playwright) de 5 flujos: ingreso, registrar producto, proponer y decidir
   una propuesta institucional, generar el anexo.
6. `docs/mantenimiento.md`: arquitectura, convenciones, patrones HTMX, cómo agregar una migración,
   despliegue, respaldo y una restauración ensayada. Política de actualización de FastHTML.

Criterio de término: todas las pruebas en verde y el piloto sigue sin notar cambios.

**Avance:**
- 1.1 hecho (26-sep-2026): `app/comun`, `app/investigacion`, `app/acreditacion` y `app/academico`
  (vacío), un commit por paquete, con una herramienta que reescribe los imports desde el árbol
  sintáctico. Dependencias de `comun` hacia `investigacion` que quedan (a resolver en la fase 2):
  `vinculos`/`importar_usuarios` → `perfiles`; `componentes/registros.py` y `rutas/inicio.py` →
  proyectos y productos.
- 1.2 hecho (26-sep-2026): las rutas de proyectos (1.094 líneas) y productos (890) son paquetes
  con un módulo por pestaña o flujo (el mayor, `productos/formulario.py`, 484). El `__init__`
  registra los módulos en orden, con la ficha al final. Verificado: las mismas 211 rutas antes y
  después, sin ciclos entre módulos y sin imports sobrantes en `app/` (pyflakes).
- 1.3 hecho (26-sep-2026): lo propio de SQLite queda en `app/comun/db.py` (sección «Dialecto
  SQL»): `HOY` (fecha local), `AHORA` (marca UTC), `DISTINTO_DE`/`IGUAL_A` (comparación con NULL),
  `vigente_hasta(col)` (antes repetida 10 veces), `marca_tiempo(delta)` para vencimientos y
  ventanas calculados en Python, y `transaccion()` en lugar de `with db.conn:`. `INSERT OR IGNORE`
  pasa a `ON CONFLICT DO NOTHING`. El docstring de `db.py` enumera qué tocaría un cambio a
  PostgreSQL (incluidos fastlite, migraciones y `LIKE`).
- 1.4 hecho (26-sep-2026): sin CDN. htmx 2.0.7, fasthtml.js, Franken UI 2.0.0 y KaTeX 0.16.21 en
  `static/vendor/`; Tailwind 3.4.17 compilado (28 KB) con los colores del tema de Franken, en lugar
  del compilador en el navegador. Se quitan daisyUI (2,9 MB por página), surreal y css-scope-inline.
  `/static` montado con StaticFiles (sin la ruta estática genérica de FastHTML). Cabeceras de
  seguridad y CSP con solo recursos propios. Verificado en el navegador: 14 páginas, modo claro y
  oscuro, estilo calculado de cada elemento antes y después (solo cambian clases del código que
  antes no tenían efecto: barra translúcida, fondos tenues, divisores con el color del tema).
  **Pendiente:** CSP estricta (sin 'unsafe-inline' ni 'unsafe-eval') requiere reemplazar unos 50
  manejadores en el HTML (onclick, hx-on) y los scripts en línea por un script propio.
- 1.5 hecho (26-sep-2026): `tests/navegador/` con Playwright (dependencia de desarrollo) sobre el
  Chrome instalado: ingreso y salida, registrar producto, proponer (con envío incompleto rechazado
  y fórmula KaTeX renderizada), decidir (con condiciones vacías rechazadas) y descargar el anexo
  XLSX. Fallan ante errores de consola, de JavaScript o de CSP (verificado provocándolos). Servidor
  aparte con base temporal. Opcionales: `pytest --navegador`. Se agrega un favicon (evitaba un 404
  en cada página).
- 1.6 hecho (26-sep-2026): `docs/mantenimiento.md` (primer día, arquitectura, convenciones,
  recetas, política de actualización de dependencias, operación, problemas frecuentes y deuda).
  Restauración ensayada con `scripts/paquete.py`: exportar en marcha, importar en vacío, negarse
  sin `--reemplazar`, reemplazar moviendo lo anterior e importar un paquete de esquema v20 con el
  código actual (aplica la migración 21). **Fase 1 completa.**

### Fase 2 — Personas, unidades y permisos (3–4 semanas)

1. Persona académica separada de la cuenta: `investigador` pasa a ser el perfil de investigación
   de una persona que puede ser docente, investigadora o ambas. Migración de datos compatible.
2. Unidades: UMSA › FCPN › CMAT › IIMAT, para acotar permisos e informes.
3. Roles con alcance y vigencia (`rol_asignado`: usuario, rol, unidad, desde, hasta):
   administración del sistema, dirección de carrera, dirección del instituto, coordinación
   académica, docente, investigador, comité de acreditación (lectura). Una función central
   `puede(usuario, accion, recurso)` reemplaza gradualmente los ~100 usos de `es_admin` y
   `es_investigador`.
4. Acceso con cuentas de la UMSA si la DTIC ofrece un proveedor (Google Workspace, LDAP u OIDC).

Criterio: matriz de permisos cubierta por pruebas.

### Fase 3 — Módulo curricular y docente mínimo (5–6 semanas)

1. Plan de estudios con versiones (resolución, vigencia): asignaturas (sigla, nombre, semestre,
   horas teóricas y prácticas, créditos, obligatoria o electiva), prerrequisitos, perfil de
   egreso y matriz asignatura–competencia.
2. Gestiones académicas (2026-I, 2026-II…) configurables.
3. Asignación docente por gestión: asignatura, paralelo, docentes y horas semanales.
4. Carga horaria por persona y gestión: docencia (de la asignación), investigación, gestión y
   otras; aviso si supera la jornada del vínculo.
5. Programas analíticos por asignatura y gestión, con versión y aprobación de la Dirección
   (mismo patrón que las propuestas institucionales).
6. Perfeccionamiento docente (hoja 13).
7. Carga por CSV del plan y de las asignaciones de los últimos 5 años.

Criterio: hojas 10 y 11 de la Guía generadas por completo.

### Fase 4 — Datos de la Carrera importados (2–3 semanas; depende de la UMSA)

Importador con vista previa (como usuarios y vínculos) de datos agregados por cohorte:
ingresantes, matriculados, egresados y titulados por modalidad, con fuente y fecha de corte
como evidencia. Indicadores de retención y titulación según las definiciones de IAC-CINDA.

### Fase 5 — Guía de Antecedentes completa (3 semanas)

1. Completar los datos de investigación que faltan (análisis de la Guía): ISBN y datos del libro
   en capítulos, fechas de patentes, instituciones y productos de redes, financiamiento interno y
   externo en USD con tipo de cambio, prestación de servicios.
2. Exportación que llena la planilla original (openpyxl, conservando estructura y fórmulas):
   hojas 3–11, 13, 19–23 y 25–28.
3. Informe de cobertura: qué celdas quedan para llenado manual.

### Fase 6 — Lanzamiento como sistema de la Carrera y el Instituto (2 semanas)

Nombre y navegación por módulos, capacitación de la Dirección y los docentes, piloto con un
semestre real y ajuste.

**Total orientativo:** 5 a 6 meses. Las fases 1 y 2 son útiles aunque luego se decida migrar;
si en la fase 0 se decide ir a Django, se omiten los puntos 1.1 a 1.4.

## 23. Diseño de la fase 2: personas, unidades y roles (propuesta, 27-sep-2026)

### Punto de partida

- **La persona es la fila de `usuario`.** Autorías (`producto_autor.investigador_id`),
  participaciones, vínculos, líneas, áreas MSC y estudiantes dirigidos apuntan a `usuario.id`.
  Los de fuera están en `persona_externa`.
- **El perfil de investigación** (`investigador`) guarda datos académicos (grado, ORCID…) y una
  copia de la categoría vigente del vínculo.
- **El vínculo** (`vinculo`) es con «el instituto»: no dice si es con el IIMAT o con la Carrera.
- **Permisos:** dos marcas, `es_admin` (56 usos) y `es_investigador` (47), la regla «todo
  `/admin/*` exige `es_admin`» (56 rutas) y los roles dentro de cada proyecto (responsable…).
  La marca de administración no se puede cambiar después de crear la cuenta.

### 1. Persona académica: la cuenta pasa a ser una capacidad de la persona

**Opción A (recomendada): la fila de `usuario` sigue siendo la persona.** Se agrega:

- `academico` (1 a 1 con `usuario`): lo que es de la persona y no de su investigación: fecha de
  nacimiento, sexo solo si el instituto lo decide más adelante, y datos de la hoja 10 de la Guía
  (sistema nacional de investigación, etc.).
- `grado_academico` (1 a n): nivel, título, institución, país y año. Reemplaza el campo único
  `investigador.grado` (se migra como primer grado).
- **Personas sin acceso:** un docente de la Carrera que no usa el portal existe como persona,
  sin contraseña utilizable (`pass_hash = '!'`, que nunca coincide), y se le puede habilitar el
  ingreso después (invitación).
- `investigador` queda como **perfil de investigación opcional**: solo quien investiga lo tiene.

Ventaja: no cambia ninguna clave foránea (autorías, participaciones, vínculos siguen igual) ni
las ~200 consultas que usan `investigador_id`. Costo: el nombre `usuario` queda corto para lo que
representa; se documenta («usuario = persona; la cuenta es opcional») sin renombrar.

**Opción B: tabla `persona` nueva** a la que apuntan todas las relaciones, y `usuario` con
`persona_id`. Conceptualmente más limpia, pero toca todas las tablas de autoría, participación y
vínculo y buena parte de las consultas: el mayor riesgo de toda la ampliación, sin beneficio
visible para los usuarios. Descartada salvo que aparezca una razón fuerte.

### 2. Unidades

Tabla `unidad` (nombre, sigla, tipo, unidad superior): UMSA › FCPN › CMAT › IIMAT, cargada en la
migración. Se usa para:

- el **vínculo**, que pasa a tener `unidad_id` (los actuales, IIMAT): una persona puede estar
  vinculada a la Carrera, al Instituto o a ambos, con categoría y jornada propias en cada uno;
- el **alcance de los roles** (abajo) y de los informes (memoria del IIMAT, datos de la Carrera);
- la **filiación** (hoy la lista fija `FILIACIONES` de config), que se deriva de la jerarquía.

### 3. Roles con alcance y vigencia

Tabla `rol_asignado`: persona, rol, unidad, desde, hasta, asignado por. Se asignan y quitan desde
«Usuarios» (lo que hoy no se puede hacer con la administración) y quedan en la auditoría.

| Rol | Alcance | Qué puede |
|---|---|---|
| Administración del sistema | global | cuentas y roles, auditoría, configuración, catálogos técnicos; no decide sobre contenido académico |
| Dirección del Instituto | IIMAT | decidir propuestas y plazos de convocatoria, catálogo de revistas y de líneas, vínculos del IIMAT, reasignar responsables, memoria y anexo de I+D+i |
| Dirección de Carrera | CMAT | plan de estudios, asignación docente y aprobación de programas (fase 3), vínculos de la Carrera, informes de la Carrera |
| Coordinación académica | CMAT | preparar asignaciones y revisar programas, sin aprobar |
| Comité de acreditación | UMSA (todo) | ver todos los informes, anexos y exportaciones; no modifica nada |
| Gestión de datos | una unidad | cargar vínculos (RR. HH.), estudiantes e importaciones de su unidad |

Los roles **derivados** no se asignan: *investigador* (tiene perfil de investigación y vínculo
con el IIMAT), *docente* (vínculo con la Carrera o asignaciones), *responsable de proyecto*
(como hoy, por proyecto).

**Transición sin sorpresas:** quienes hoy tienen `es_admin` reciben Administración del sistema y
Dirección del Instituto, así nadie pierde lo que hoy puede hacer. Luego la dirección decide a
quién le quita cuál.

### 4. Un solo punto de decisión: `puede(usuario, accion, unidad=None)`

- Tabla de acciones → roles en un módulo (`app/comun/permisos.py`), p. ej.
  `"decidir_propuestas": {"direccion_instituto"}`, `"ver_informes": {"direccion_instituto",
  "direccion_carrera", "comite_acreditacion"}`.
- Los roles vigentes se cargan al validar la sesión (Beforeware), una consulta por petición.
- Se reemplazan los 56 `es_admin` y la regla del prefijo `/admin` módulo por módulo, con una
  prueba por acción y rol (matriz de permisos). Mientras dure la transición, `es_admin` se deriva
  de los roles, para que el código aún no migrado siga funcionando igual.
- Resuelve la deuda de la fase 1: `vinculos` e `importar_usuarios` dejan de escribir en
  `investigador` (la categoría vigente se calcula del vínculo) y `componentes/registros.py` e
  `inicio` se reparten según el paquete.

### 5. Fecha de nacimiento

En `academico`. La carga la administración (formulario o CSV de RR. HH., junto al historial de
vínculos). Solo la ven quienes tengan el permiso `ver_datos_personales` y los informes usan solo
tramos de edad (hoja 11). Se avisa a cada académico en su perfil que el instituto la registra
para la acreditación.

### 6. Acceso con cuentas de la UMSA (opcional)

Solo si la DTIC ofrece un proveedor (Google Workspace para @umsa.bo, LDAP u OIDC). No bloquea lo
demás: se evalúa al final de la fase.

### Orden de ejecución (cada paso se puede desplegar solo)

1. **Unidades** y `vinculo.unidad_id` (los existentes pasan al IIMAT).
2. **Roles**: `rol_asignado`, `puede()`, carga en la sesión, pantalla para asignarlos y migración
   de `es_admin`. Matriz de permisos en las pruebas.
3. **Reemplazo de `es_admin`** por acciones, módulo por módulo.
4. **Persona académica**: `academico`, `grado_academico`, personas sin acceso, fecha de nacimiento,
   y fin de las dependencias de `comun` hacia `investigacion`.
5. Acceso con cuentas de la UMSA, si corresponde.

Estimación: 3 a 4 semanas (sin el paso 5).

**Decidido (27-sep-2026):**
1. La tabla de roles refleja el trabajo de ambas direcciones (incluidas Coordinación académica y
   Gestión de datos; el Comité de acreditación ve todo, también lo de la Carrera).
2. Los roles los asigna **solo Administración del sistema**, a pedido de las direcciones.
3. Cada académico **ve su propia fecha de nacimiento** en su perfil, sin poder editarla.
4. La DTIC ofrece inicio de sesión institucional: el paso 5 se hace (falta saber el proveedor).

**Avance:**
- Paso 1 hecho (27-sep-2026): tabla `unidad` (UMSA › FCPN › CMAT › IIMAT, migración 0022) y
  `vinculo.unidad_id` obligatorio (tabla reconstruida; los vínculos existentes quedan con el IIMAT,
  verificado sobre una copia de la base de desarrollo). `app/comun/unidades.py`. Todas las
  funciones de `vinculos` reciben la unidad (por omisión el IIMAT, así los informes de
  investigación no cambian); la superposición se valida por unidad. Ninguna consulta a `vinculo`
  queda fuera del módulo (`personas_en_rango` reemplaza dos que no filtraban por unidad: una
  docente solo de la Carrera hacía fallar la memoria). Pantalla de vínculos con selector
  IIMAT/CMAT e importación de RR. HH. con columna `unidad`. Las categorías de la Carrera son, por
  ahora, las mismas del Instituto: revisar cuando se defina la «jerarquía académica» de la hoja 10.
- Paso 2 hecho (27-sep-2026): tabla `rol_asignado` (migración 0023); quienes eran administradores
  reciben Administración del sistema (UMSA) y Dirección del Instituto (IIMAT); se elimina la
  columna `usuario.es_admin` (verificado en la base de desarrollo, que el servidor migró solo).
  `app/comun/permisos.py`: ROLES, ACCIONES (tabla inicial), `puede()`, asignar, quitar y el
  resguardo de no quedarse sin Administración del sistema. Alcance: los roles de la UMSA cubren
  todo; los demás, solo su unidad (el IIMAT está dentro de la CMAT, pero la Dirección de Carrera no
  decide sobre el Instituto). «Quitar» = deja de regir hoy (último día, ayer; si empezó hoy, se
  anula). Pantalla «Roles» en Usuarios, solo para Administración del sistema, con la dirección que
  lo pidió. `es_admin` se calcula de los roles mientras el paso 3 reemplaza sus ~50 usos. Los
  avisos de propuestas van a la Dirección del Instituto. Matriz de permisos en `tests/test_roles.py`.
- Paso 3 hecho (27-sep-2026): ninguna comprobación usa ya `es_admin` (desaparece también el cálculo
  transitorio). Las 64 rutas `/admin` se autorizan con `REGLAS_ADMIN` (lo no previsto se deniega;
  una prueba verifica que cada ruta tenga regla). Dentro, `puede()` con acciones nuevas:
  `ver_usuarios`, `gestionar_personas_externas`, `ver_propuestas`, `ver_evidencias`,
  `ver_cv_ajeno`. Vínculos por unidad (pantalla, periodos, importación, desactivar con término).
  Menú y botones según el rol. Memoria y anexo son informes del IIMAT: los ven la Dirección del
  Instituto y el Comité, no la Dirección de Carrera ni Administración del sistema. Matriz por rol
  en `tests/test_permisos_rutas.py`.
- Paso 4a hecho (27-sep-2026): `comun` ya no importa nada de `investigacion`. La categoría vigente
  se calcula del vínculo (`vinculos.sql_categoria_vigente`, migración 0024 elimina
  `investigador.categoria` y su sincronización horaria); CATEGORIAS y la corrección de la
  categoría pasan a `vinculos`. Se mueven a su paquete el componente de perfil, la parte de
  `registros` propia de investigación (adjuntos y vinculación a proyectos), la página de coautores
  externos y los indicadores de estudiantes (a `acreditacion`); la página de inicio pasa a
  `app/inicio.py`.
