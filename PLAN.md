# TAU: diseño y estado

**TAU | Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática.** Nació
como «Portal de Investigación» del IIMAT y se amplió (secciones 22 a 24) a la gestión académica de
la Carrera y la acreditación; el nombre se adoptó el 27 de septiembre de 2026.

> **Contexto:** Instituto de Investigación Matemática (IIMAT) de la Carrera de Matemática (CMAT),
> Facultad de Ciencias Puras y Naturales (FCPN), Universidad Mayor de San Andrés (UMSA), La Paz,
> Bolivia. TAU sostiene la **acreditación de la Carrera y del Instituto ante IAC-CINDA**.
> Zona horaria America/La_Paz; montos en bolivianos (Bs). Ver la sección 13.

Documento de diseño del sistema: qué hace, cómo está organizado, qué se decidió y qué queda
pendiente. Para instalarlo y trabajar en el código, vea el [README](README.md); para usarlo, la
[guía de uso](docs/guia-de-uso.md); para ponerlo en producción, la [guía de despliegue](docs/despliegue.md).

## 1. Visión

Sistema interno donde cada investigador del instituto ingresa con su cuenta y mantiene al día su
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

Las marcadas **(confirmada)** las tomó el equipo durante el desarrollo y la Dirección las confirmó
el 1-oct-2026 sin cambios.

- **Informe del instituto:** solo productos indexados o arbitrados. Si están enviados o en
  preparación, todavía no cuentan (cuentan los aceptados y publicados) **(confirmada)**.
- **Qué índices cuentan como «indexado»:** WoS (SCIE y ESCI), Scopus, SciELO, MathSciNet y
  zbMATH sí; Latindex Catálogo no (cuenta como arbitrado: evalúa la calidad editorial, no indexa
  citas) **(confirmada)**.
- **Permisos sobre registros:** editan el creador y los coautores o participantes del instituto;
  elimina solo el creador **(confirmada)**.
- **Adjuntos** (certificados, etc.): solo los ven quienes pueden editar el registro y la administración.
- **Co-responsables** tienen los mismos permisos que el responsable, incluida la aprobación y la
  asignación de carga **(confirmada)**.
- **Proyectos** privados: los ven sus participantes (también quienes ya salieron), la Dirección del
  Instituto y el Comité de acreditación; no la Administración del sistema ni el perfil público
  **(confirmada)**.
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
- **Ingreso:** usuario y contraseña propios del sistema; sin SSO ni LDAP en el piloto.

## 9. Pendiente

**Antes de producción** (ver [despliegue](docs/despliegue.md) o [Fly.io](docs/despliegue-fly.md)):
- *(Hecho en la fase 1.)* Tailwind compilado localmente y htmx, Franken UI y KaTeX servidos por el
  propio sistema, sin CDN.
- Configurar SMTP, `PORTAL_URL`, `PORTAL_SECRET_KEY`, `PORTAL_HTTPS_ONLY=1` y `PORTAL_CONTACTO`.
- *(Hecho el 1-oct-2026.)* Revisar con el instituto las decisiones marcadas «(confirmar)».
- Designar un suplente del responsable técnico y fijar la política de respaldos (diarios, fuera del
  servidor, con ensayo de restauración cada semestre). Propuesta para la reunión de despliegue:
  documento «Fundamento técnico de TAU».
- Elegir dónde alojar el piloto (servidor del instituto o Fly.io) según su política sobre datos
  personales en proveedores externos; usar un dominio propio desde el inicio facilita mudarse.
- Si se usa Fly.io: probar un despliegue real. La imagen se construyó y se probó localmente con
  Podman (arranque con Litestream, paquete de datos y restauración tras destruir el volumen);
  falta probarla en la plataforma, con Tigris como réplica.

**Funcionalidad que el plan original incluía y aún no está:**
- *(Hecho el 2-oct-2026, §47.)* Administrar los catálogos (tipos de actividad y de producto, índices)
  desde la interfaz.
- *(Hecho el 1-oct-2026, §41 y §42.)* Fusionar personas externas duplicadas, y vincular una persona
  externa a su cuenta si luego la recibe.
- *(Hecho el 2-oct-2026, §45.)* Áreas MSC en los productos.
- *(Hecho el 2-oct-2026, §46.)* Enlace formal entre un preprint y su versión publicada, como
  registros separados.

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

### Interpretaciones propias (confirmadas el 1-oct-2026)

- Las restricciones por categoría se aplican a los proyectos **institucionales**. Un proyecto
  individual lo puede registrar cualquier investigador(a) y queda como responsable.
- «Ligado a un proyecto institucional» significa que el producto o actividad está **aprobado** en
  un proyecto institucional (no en formulación) vigente en el periodo del informe.
- *(Superada.)* «La categoría no guarda historial»: la reemplazaron los periodos de vínculo (§12,
  §23 y §25). La categoría la define la Dirección de Carrera y los informes usan la de cada fecha.
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
| Desactivar una cuenta | El sistema pregunta si también termina el vínculo y en qué fecha. |
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
- *(Resuelto en la fase 3.)* El cálculo por jornada: el anexo usa JCE = carga contratada / 160 (§24).

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
  manual de criterios vigente y hacer una tabla de correspondencia criterio → dato del sistema →
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

Tabla completa (criterio → qué registra el sistema → brecha, con estado): 
https://claude.ai/artifact/VuTd7X3jxFy3Fx4JgwH4wU (privada; compartir desde el menú de la página).

- Base: criterios de pregrado de IAC-CINDA (junio 2025, v1.2), que aplican a la Carrera de
  Matemática. **Pendiente:** confirmar con IAC-CINDA qué conjunto de criterios corresponde al
  Instituto (el Modelo 2025 describe procesos para instituciones, carreras, maestrías y doctorados).
- De 33 criterios revisados que tocan la investigación: 15 cubiertos, 16 parciales, 2 brechas; 12
  más dependen de políticas o procesos fuera del sistema.

**Prioridades para el sistema** (por aporte a la acreditación):

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
  obras de otras personas: el sistema lo advierte cuando hay más de 40 obras por año.
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
  externos), 3.6.1 impacto; lista de lo que el sistema aún no registra; «Datos y método».
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
el 26 de septiembre de 2026, toda petición que modifica datos debe venir del propio sistema según
`Origin` (o `Referer`, si falta): el host de la petición, `PORTAL_URL` o `PORTAL_ORIGENES_EXTRA`.
Es la verificación de origen que recomienda OWASP; no requiere tokens ni cambiar formularios. Sin
`Origin` ni `Referer` se admite (no es un navegador con la sesión de otra persona).

Verificado con el servidor de desarrollo: un origen del propio sistema se acepta (200) y uno de otro
subdominio se rechaza (403).

## 21. Líneas de investigación institucionales

La Guía de Antecedentes de IAC-CINDA pide la línea de investigación en proyectos, desarrollo
académico, publicaciones, libros y patentes (hojas 19–23 y 25), y su hoja 2 fija las seis líneas del
programa: Sistemas Dinámicos, Estructuras Algebraicas Ordenadas, Teoría de Control, Modelos
Matemáticos y Computación, Optimización Matemática y Áreas Fundamentales Complementarias (cargadas
por la migración 0021).

- **Las líneas cambian:** cada una tiene vigencia (`vigente_desde`, vacío = desde antes del sistema;
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
- «Jerarquía académica» de la hoja 10: ¿categoría del sistema o escalafón docente?
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
- Nombre (27 de septiembre de 2026): **TAU | Sistema Integrado de Gestión Académica y Científica de
  la Carrera de Matemática**. Se configura con `PORTAL_SISTEMA` y `PORTAL_SISTEMA_DESCRIPCION`; los
  nombres técnicos (variables `PORTAL_*`, `portal.db`, servicio `portal`, aplicación de Fly.io)
  conservan «portal» para no romper las instalaciones existentes.

**Pendiente de la fase 0:** qué datos entrega el sistema académico de la UMSA (condiciona la
fase 4) y la «jerarquía académica» de la hoja 10. No bloquean las fases 1 a 3.

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
- **Personas sin acceso:** un docente de la Carrera que no usa el sistema existe como persona,
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
  vinculada a la Carrera, al Instituto o a ambos, con categoría y jornada propias en cada uno.
  *Revisado el 28-sep-2026 (sección 25): hay una sola dependencia, la Carrera;*
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

> *Nota (2-oct-2026):* esta tabla es la propuesta original. Desde la dependencia única (§25, 28-sep-2026)
> **solo la Dirección de Carrera** define categoría, vínculo y carga; la Dirección del Instituto y Gestión
> de datos ya no gestionan vínculos. Lo vigente está en `ACCIONES` y `DESCRIPCIONES`
> (`app/comun/permisos.py`).

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
- Paso 4b hecho (27-sep-2026): `app/comun/academicos.py`. Varios grados por persona
  (`grado_academico`, migración 0025; el grado único se migra como primer grado y desaparece
  `investigador.grado`); el que se muestra es el de mayor nivel. Se editan en «Mi perfil» y en la
  ficha académica de Usuarios (direcciones y Gestión de datos; Administración del sistema la ve).
  Personas sin acceso (`pass_hash = '!'`): no ingresan ni se habilitan solas con «¿Olvidó su
  contraseña?»; «Habilitar acceso» les da una contraseña temporal. Ya no se exige que una cuenta
  sea de investigador o de administración (docentes). Vínculos para cualquier persona, con resumen
  por unidad en el listado. De paso: la tabla que se devolvía al crear una cuenta se armaba antes
  de crearla (la nueva no aparecía hasta recargar).
- Paso 4c hecho (27-sep-2026): fecha de nacimiento en `datos_personales` (migración 0026, tabla
  aparte para que ninguna consulta general la arrastre). La registra y la ve solo Administración
  del sistema (ficha académica); la persona la ve en «Mi perfil» o en «Mis datos personales», sin
  editarla, con el aviso. `academicos.tramo_edad` para los informes (hasta 29, 30–39, 40–49, 50–59,
  60 o más). No aparece en perfiles públicos, API ni en el detalle de la auditoría.
  **Pendiente:** carga masiva de fechas de nacimiento desde RR. HH., si hace falta (hoy, una por una).
- **Fase 2: pasos 1 a 4 completos.** El paso 5 (acceso con cuentas de la UMSA) espera que la DTIC
  confirme el proveedor.

## 24. Fase 3: módulo curricular y docente (27-sep-2026)

Fuente: planes de estudio 2017 (Resolución HCU 041/2017) de la Licenciatura en Matemática, la
Licenciatura en Matemática Aplicada, la Maestría en Matemática y la Maestría en Matemática
Aplicada (PDF de la Dirección Académica). Licenciaturas: 8 semestres, tres ciclos, horas
semanales teóricas/prácticas/laboratorio, semestres de 20 semanas, nota mínima 51 %. Maestrías:
4 semestres en créditos (1 crédito = 40 horas académicas), nota mínima 66 %.

**Decidido:**
1. Gestiones: I-2026 y II-2026 (semestres), INV-2026 (invierno, julio) y **VER-2026** (verano, enero;
   «VER» y no «V» para no leerlo como el número romano 5). El verano se cuenta con la gestión
   anterior: VER-2026 se dicta en enero de 2027. Orden de la gestión 2026: I → INV → II → VER. El
   sistema guarda tipo, año y fechas; el código solo se muestra, y el orden sale de las fechas.
2. El plan 2017 y el nuevo (desde 2027) coexisten mientras haya estudiantes en el antiguo, con una
   tabla de equivalencias entre asignaturas.
3. Las asignaturas de otras carreras (FIS, QMF, QMI, QMC, INF, BIO, ECO) figuran en el plan, sin
   asignación docente (las dicta otra unidad).
4. Carga horaria: docencia (se calcula de la asignación), investigación, gestión (cargos),
   extensión y servicios, y otras.
5. Las inconsistencias de los PDF se cargan tal como están y quedan marcadas para revisión.

**Pasos:** 3.1 catálogo curricular y carga de los planes 2017 · 3.2 gestiones académicas · 3.3
oferta y asignación docente · 3.4 carga horaria · 3.5 programas analíticos · 3.6 perfeccionamiento
docente · equivalencias cuando llegue el plan nuevo.

**Avance:**
- 3.1 hecho (27-sep-2026): tablas programa, plan_estudios (con vigencia), asignatura (catálogo único
  por sigla; `de_la_carrera` = 0 para FIS, QMF, QMI, QMC, INF, BIO, ECO), plan_asignatura (semestre,
  ciclo, tipo, horas o créditos; casillas de electiva sin asignatura), requisito (sigla o
  «egresado») y observacion_plan (migración 0027). Los cuatro planes 2017 en `datos/planes/`
  (transcritos de los PDF por la posición de las columnas y verificados contra los totales) y
  cargados por la migración 0028: 123 asignaturas (92 de la Carrera). Observaciones marcadas:
  horas de laboratorio que no cuadran en ambas licenciaturas (720/680 y 1.080/1.160), MAT-241 y
  MAT-242 inexistentes, MAT-278 repetida, requisito probable FIS-377 en FIS-387, MAT-382, erratas
  «Cientítica» e «Intiligencia», «Algebra» sin tilde en la maestría aplicada. Pantallas
  /docencia/planes (consulta para todos; resolver observaciones: Dirección de Carrera y Coordinación
  académica).
  Nota: cada base de prueba carga los planes; la suite tarda ~10 s más.
- 3.2 y 3.3 hechos (27-sep-2026): `gestion_academica` (año, tipo, fechas; fechas por omisión que la
  Dirección ajusta), `oferta` (asignatura de la Carrera, gestión, paralelo, inscritos) y
  `oferta_docente` (titular o auxiliar; las horas semanales se quitaron en 3.4) — migración 0029.
  Pantallas /docencia/oferta y /docencia/gestiones con pestañas de la sección; acción
  `gestionar_oferta` (Dirección de Carrera y Coordinación académica). Aviso (no bloqueo) si el
  docente no tiene vínculo con la Carrera en la gestión. `oferta.horas_de_docencia` alimentará la
  carga horaria (3.4).
- 3.3b hecho (27-sep-2026): `app/academico/importar_oferta.py`: CSV con una fila por docente de cada
  paralelo; reemplaza la oferta de las gestiones incluidas (reimportar no duplica), todo o nada por
  gestión, crea las gestiones del año si faltan, horas y rol por omisión, avisos de docentes sin
  vínculo con la Carrera. Vista previa y confirmación en «Oferta y docentes».
- 3.4 hecho (27-sep-2026). Reglas acordadas: la carga se cuenta en unidades de 32 h/mes; cada
  persona tiene **una** carga contratada por semestre (I o II) de 32, 64, 96, 128 o 160 h/mes,
  que registra y distribuye la Dirección de Carrera; cada materia como titular (grado o maestría)
  son 32 h/mes; investigación, extensión, gestión y otras, múltiplos de 32 h/mes. Los auxiliares
  van aparte (sin carga, por ahora). Los cursos de verano e invierno no forman parte de la carga
  (docencia dictada) y solo los dictan titulares de la Carrera (los interinos tienen contratos por
  semestre). Migración 0030: `carga_semestral` y `carga_actividad`; se quitan las horas semanales
  de `oferta_docente` (y la columna `horas` del CSV de oferta). `app/academico/carga.py` (resumen
  con avisos, copia del semestre anterior) y pestaña /docencia/carga (acciones `ver_carga` y
  `asignar_carga`). El anexo calcula la JCE como carga contratada / 160 (sin carga registrada,
  jornada del vínculo × 4); el formulario de vínculos ya no pide la jornada (se conserva la
  histórica). Pendiente si hace falta: importar por CSV la carga de semestres pasados.
- 3.4, revisión (27-sep-2026): la carga contratada se registra en el **vínculo con la Carrera**
  (Usuarios → Vínculo, pestaña CMAT, también al agregar un periodo): total y distribución por
  actividad (docencia, investigación, extensión, gestión, otras) en múltiplos de 32 h/mes que suman
  el total. Un cambio de carga es un periodo nuevo. Migración 0031: columnas `horas_contratadas` y
  `carga_*` en `vinculo`; lo registrado por semestre pasa al vínculo con la Carrera vigente al
  inicio de ese semestre (sin ese vínculo, se pierde) y se eliminan `carga_semestral` y
  `carga_actividad`. La pestaña «Carga horaria» queda de consulta: por semestre, según el vínculo
  vigente al inicio, compara la docencia prevista con la asignada en la oferta. Se retira la
  acción `asignar_carga`: registra quien gestiona los vínculos de la Carrera (`gestionar_vinculos`
  en CMAT: Dirección de Carrera y Gestión de datos).
- Oferta inicial de troncales (27-sep-2026): al crear las gestiones de un año, los semestres I y II
  se ofertan con las troncales de las licenciaturas (obligatorias y trabajo final de la Carrera; 34
  del plan 2017) en el paralelo A, sin docente. Un plan se considera mientras tenga estudiantes: del
  primer ingreso al último ingreso + su duración. Las electivas, otros paralelos y los docentes se
  agregan a mano; una troncal se puede quitar y volver a crear el año no la repone. Botón «Agregar
  las troncales» para completar semestres ya creados. La importación de gestiones pasadas no agrega
  troncales (el archivo manda).

## 25. Dependencia única, clases de proyecto institucional y proyectos individuales (28-sep-2026)

**Decisiones del instituto:**

1. **Una sola dependencia.** El vínculo de cada persona es con la Carrera de Matemática; el
   Instituto forma parte de ella, sin periodos diferenciados. **Solo la Dirección de Carrera**
   define la categoría y el vínculo: altas, cambios, término y carga horaria contratada. La
   Dirección del Instituto gestiona el ciclo de vida y los flujos de trabajo (actividades y
   productos) de los proyectos, como unidades integradas por sus participantes, incluidos los
   externos, tengan o no carga horaria asignada para investigación o extensión.
2. **Dos clases de proyecto institucional:** de investigación y de interacción social
   (extensión). Solo titulares y contratados pueden proponerlos (ya regía).
3. Quien registra un **proyecto individual** puede eliminarlo.

**Hecho (28-sep-2026):**

- Migración 0032: los periodos con el Instituto pasan a la Carrera; los que se superponían con
  uno de la Carrera se descartan (manda el de la Carrera, que lleva la carga). `vinculos` ya no
  recibe `unidad`: todo es con la Carrera (`vinculos.carrera()`); la categoría vigente y los
  informes usan ese único historial.
- `gestionar_vinculos` = Dirección de Carrera (antes también Dirección del Instituto y Gestión de
  datos). La ventana «Vínculo» ya no tiene selector de unidad. Al crear cuentas (formulario o CSV),
  la categoría solo se toma si quien las crea tiene la Dirección de Carrera; si no, la cuenta queda
  «Sin categoría». «Importar historial» ya no lleva columna `unidad` (si viene, se ignora).
- Migración 0033: `proyecto.clase` (`investigacion` | `interaccion_social`; vacío en los
  individuales; los institucionales existentes, investigación). Se elige al proponer. Las líneas
  de investigación son obligatorias en los de investigación y opcionales en los de interacción
  social. La clase figura en la propuesta, la bandeja y el XLSX de la convocatoria, la ficha del
  proyecto, la memoria (institucionales separados por clase) y el anexo.
- Proyectos individuales: botón «Eliminar» para su responsable (o quien lo registró). Se borran
  participantes, objetivos, contrapartes y enlaces; los productos y actividades siguen en el
  registro de sus autores. Los institucionales no se eliminan.

**Confirmado (28-sep-2026):** las líneas de investigación son opcionales en los proyectos de
interacción social, y el anexo de I+D+i (3.6.3 h) lista todos los proyectos vigentes con su clase.

## 26. Término del vínculo y carga horaria en proyectos (28-sep-2026)

**Decisiones del instituto:**

1. Contratados, interinos e invitados se vinculan por un periodo con **fecha de término
   obligatoria**. El titular es permanente (sin término), pero su vínculo se puede terminar a mano
   por retiro, despido, fallecimiento o renuncia.
2. Al agregar participantes a un proyecto **institucional**, el responsable indica su carga horaria
   en el proyecto (puede no tener). Sale de la carga de investigación (proyectos de investigación) o
   de extensión (interacción social) que la Dirección de Carrera asignó en su vínculo, y rige solo
   mientras ese vínculo está vigente. Los proyectos individuales no asignan carga.
3. Si el vínculo termina durante el proyecto, la persona puede seguir como participante, pero figura
   sin carga desde entonces, y se avisa al responsable. En un nuevo periodo de vínculo la carga no se
   reasigna sola: se avisa a los responsables de los proyectos donde tuvo carga, **solo mientras le
   quede carga libre** de esa actividad (si otro proyecto ya se la asignó toda, el aviso no aparece
   o desaparece), y el responsable decide.

**Hecho (28-sep-2026):**

- Migración 0034: `vinculo.motivo_termino`; `participante_carga` (participante, periodo de vínculo,
  horas, desde; una por participante y periodo); `aviso_carga` (desvinculado | nuevo_vinculo; se
  crea una vez y se atiende).
- `vinculos.regla_termino`: término obligatorio para contratado, interino e invitado (salvo periodos
  antiguos con ingreso desconocido); un titular nuevo no lleva término futuro. Se aplica al agregar
  periodos, al cambiar de categoría (ahora con «hasta»; cierra el periodo vigente aunque tuviera
  término posterior), al crear cuentas con categoría y al importar el historial. `terminar` guarda
  el motivo. Al corregir un periodo, la investigación/extensión no puede bajar de lo asignado en
  proyectos.
- `app/investigacion/carga_proyectos.py`: disponible, asignar, historial, avisos. Los avisos se
  revisan cuando cambia un vínculo (`vinculos.OYENTES`, para no importar desde `comun`), al asignar
  y en el mantenimiento horario (términos que llegan con la fecha). Correos a los responsables
  (`avisos.carga_desvinculado`, `avisos.carga_nuevo_vinculo`); los avisos cuentan en los
  pendientes del proyecto y de la barra.
- Pantallas: columna «Carga (h/mes)» en Participantes, carga al agregar a alguien del instituto,
  avisos en Pendientes, motivo en «Terminar el vínculo» y al desactivar una cuenta; en Docencia →
  Carga horaria, la carga de cada persona en proyectos.

**Por hacer si hace falta:** carga en proyectos en el informe del proyecto y en el anexo.

## 27. Cargo y unidad o grupo calculados (28-sep-2026)

**Decisión del instituto:** en el perfil ya no se editan «Cargo» ni «Unidad o grupo».

- **Cargo:** «Docente Investigador» si la persona tiene carga de investigación en su vínculo
  vigente; «Docente» si no. Sin vínculo vigente, sin cargo (decisión del agente, por confirmar).
- **Unidad o grupo,** en este orden: proyectos de los que es responsable (y co-responsable),
  proyectos en que participa, el detalle de «Extensión y servicios» y el de «Gestión» del vínculo;
  si nada aplica, «Carrera de Matemática». Solo proyectos vigentes (no en formulación ni
  finalizados).

**Hecho:** migración 0035: detalle por actividad en el vínculo (`detalle_investigacion`,
`_extension`, `_gestion`, `_otras`; el detalle único anterior pasa a la actividad si solo una tenía
horas, si no a la nota del periodo) y se quitan `investigador.cargo` y `.unidad`.
`app/comun/adscripcion.py` calcula ambos (solo consulta tablas); los usan el perfil, el directorio
(y su búsqueda), la página pública, la API, el CV y la afiliación que se muestra de cada persona en
proyectos y autorías. El perfil completo ya no cuenta cargo ni unidad.

## 28. Usabilidad e informes: evaluación y punto 1 (28-sep-2026)

Evaluación publicada como página (stack adecuado; la brecha está en la experiencia por rol y los
informes de docencia) con un orden de trabajo de 8 puntos: 1 inicio por rol y «Mi docencia»; 2
informe de carga docente e indicadores del cuerpo académico; 3 componente de tablas; 4 tablero de
calidad de datos; 5 ficha de docente y acciones masivas; 6 centro de avisos; 7 series con gráficos y
trazabilidad en el anexo; 8 SSO UMSA, PDF con membrete, Guía de Antecedentes.

**Punto 1, hecho:** «Para hoy» en el inicio (Lo mío, Dirección de Carrera, Dirección del Instituto,
Acreditación) y «Mi docencia» (`/docencia/mia`; `/docencia` abre ahí para quien tiene vínculo o
materias). Funciones en `app/academico/carga.py`: `semestre_de_referencia`, `contratos_por_vencer`,
`vigentes_sin_carga`, `gestiones_de`, `materias_con_detalle`, `proyectos_con_carga`. Los invitados y
externos sin materias ya no generan el aviso «Falta registrar la carga contratada».

## 29. Informes de docencia (punto 2 de la evaluación, 28-sep-2026)

- `app/acreditacion/cuerpo_academico.py`: `carga_docente(gestion)` (por persona, por categoría y
  total; JCE; docencia prevista y asignada; carga en proyectos; inscripciones del semestre por
  JCE) e `indicadores_anio(anio)` / `indicadores(desde, hasta)` (vinculados y JCE de
  `anexo.cuerpo_academico`; % con doctorado y con posgrado según los grados obtenidos hasta ese
  año; tramos de edad; % de la carga en investigación; % con proyecto vigente; inscripciones por
  JCE del II semestre del año, o del I si el II aún no empezó).
- Pantallas `/informes/carga-docente` (`ver_carga`) y `/informes/cuerpo-academico`
  (`ver_informes_institucionales`), imprimibles y en XLSX; tarjetas en «Informes» y enlace desde
  Docencia → Carga horaria.
- **Límite conocido:** «inscripciones» suma inscritos por paralelo; la matrícula real (y con ella
  la razón estudiantes/JCE que pide IAC-CINDA) depende de los datos del sistema académico de la UMSA
  (fase 4). La carga de un periodo largo de vínculo se aplica a todos sus años: para series
  históricas exactas, registre la carga en periodos por gestión.
- Se corrigió el seed: los grados de ejemplo tenían años anteriores a 1940 y la validación los
  descartaba sin avisar.

## 30. Componente de tablas (punto 3 de la evaluación, 28-sep-2026)

`static/js/tablas.js`: toda `<table data-tabla="…">` gana orden por columna (números, fechas y texto en
español; los vacíos al final), filtro por texto con conteo «N de M filas» y «Descargar CSV» de lo
visible (UTF-8 con BOM, fórmulas neutralizadas como en el servidor). Se reaplica con htmx (`htmx:load`)
y se actualiza si htmx reemplaza las filas (`htmx:afterSettle`). Aplicado en carga horaria, oferta,
usuarios (sin filtro: tiene buscador del servidor), propuestas, revistas, personas externas,
estudiantes, participantes, informe de carga docente, memoria por investigador y proyectos del anexo.
No se aplica a tablas por grupos (planes por semestre) ni a las series por año de los informes.

## 31. Tablero de calidad de datos (punto 4 de la evaluación, 28-sep-2026)

`app/acreditacion/calidad.py` (solo consulta) y `/informes/calidad` (acción `ver_calidad_datos`:
direcciones, Coordinación académica, Comité y Administración del sistema). Doce revisiones, cada una
con a qué afecta, quién la corrige y sus registros con enlace: periodos sin término, docentes sin
carga, vínculos sin ingreso, investigadores sin vínculo, sin grado, sin fecha de nacimiento, perfiles
sin ORCID o bajo el 50 %, publicaciones que no cuentan hasta completarse (reutiliza
`memoria(...)["por_confirmar"]` de la ventana del anexo), paralelos sin docente o sin inscritos,
observaciones de planes, proyectos sin ámbito y de investigación sin línea. El inicio muestra el total
en «Para hoy». Agregar una revisión: una función que devuelva `_chequeo(...)` y sumarla a `CHEQUEOS`.

## 32. Ficha de docente y acciones masivas (punto 5 de la evaluación, 28-sep-2026)

- Ficha `/docencia/docentes/{uid}` (`ver_carga`; la propia persona va a «Mi docencia»): reutiliza las
  tarjetas de «Mi docencia»; botón «Vínculo y carga» (abre la ventana de vínculo) para la Dirección de
  Carrera. Los nombres de «Carga horaria» enlazan a la ficha.
- Oferta: «Copiar de …» (`oferta.copiar`: paralelos del mismo semestre del año anterior que faltan,
  sin inscritos, con docentes opcionales y las reglas de `asignar`) y «Asignar en grilla»
  (`oferta.fijar_titular`: un titular por paralelo, reemplaza al anterior, respeta la regla de
  temporada).
- Renovaciones `/docencia/renovaciones` (`gestionar_vinculos` en la Carrera):
  `carga.candidatos_renovacion` (último periodo con término, terminado en los 150 días previos al
  semestre, sin periodo nuevo) y `carga.renovar` (misma categoría y carga; la carga en proyectos no
  pasa: avisos a responsables). El aviso del inicio sobre vínculos que vencen enlaza aquí.

## 33. Centro de avisos y resumen semanal (punto 6 de la evaluación, 28-sep-2026)

- Migración 0036: tabla `notificacion` (asunto, texto, url interna, leída, resumida) y
  `usuario.frecuencia_avisos` (`inmediato` | `semanal` | `nunca`; reemplaza `avisos_correo`: desactivado
  = `nunca`) con `ultimo_resumen`.
- `app/comun/notificaciones.py`: `avisar(u, asunto, texto, url, cuerpo_correo)` registra el aviso y
  envía el correo si la preferencia es inmediata; `resumen_semanal()` (en el mantenimiento horario)
  envía a quien lo prefiere los avisos sin leer ni resumir, a lo más uno cada 7 días. Todos los avisos
  de `app/investigacion/avisos.py` pasan por ahí (mismos asuntos y enlaces de siempre).
- Pantallas: campana en la barra (se carga aparte, `/avisos/campana`), `/avisos` (historial y
  preferencia), `/avisos/{id}` (marca leído y lleva a donde se atiende). «Mi perfil» enlaza a la
  preferencia.

## 34. Series con gráficos y trazabilidad (punto 7 de la evaluación, 28-sep-2026)

- `app/comun/componentes/graficos.py`: `barras()` dibuja barras apiladas en SVG en el servidor (sin
  JavaScript ni bibliotecas externas: la CSP no las admite y así se imprimen igual). Cada barra puede
  enlazar a sus registros; `role="img"` con los datos en `aria-label` y un `title` por barra.
- Anexo: `anexo.INDICADORES` (nombre, clase de registro y regla de cada fila del resumen por año) y
  `registros_del_anio()`, que devuelve los registros de cada indicador; la cifra es su cantidad (JCE y
  citas suman). `detalle()` alimenta `/informes/acreditacion/detalle?indicador=&anio=` (con
  `categoria` para el cuerpo académico), con la misma autorización del anexo. Una prueba verifica que
  cada cifra de cada año coincide con sus registros. Los ceros no enlazan.
- Anexo: sección «Tendencias» (nueve gráficos del periodo); las cifras destacadas enlazan a su
  criterio.
- Memoria: `informes.serie_anual()` y la sección «Evolución» (cinco años calendario que terminan en el
  periodo elegido; cada barra abre la memoria de su año).

## 35. PDF con membrete (punto 8 de la evaluación, primera parte, 28-sep-2026)

- Decisión (28-sep-2026): el PDF se sigue generando con la impresión del navegador (las fórmulas
  salen con KaTeX; sin dependencias nuevas). Un generador en el servidor (WeasyPrint) se evaluará
  solo si hacen falta envíos automáticos de PDF.
- Decisión (28-sep-2026): **todos los informes llevan los logos del IIMAT y de la Carrera**.
- `hoja()` agrega el membrete (logos a los lados; universidad, facultad, Carrera e Instituto al
  centro, desde `config`: `UNIVERSIDAD`, `FACULTAD`, `NOMBRE_CARRERA`, `NOMBRE_INSTITUTO`) y, con
  cajas de margen de `@page`, el pie de cada página: título del informe (del primer H1) y «Página X
  de Y». Chrome y Edge las dibujan; los demás navegadores las omiten.
- Logos: los originales que entregó la Dirección están en `static/img/membrete/logo_*.png` (también
  UMSA y FCPN, por ahora sin uso); el membrete usa copias recortadas de 300 px de alto (`iimat.png`,
  `cmat.png`, ≈50 KB). Para cambiar un logo, reemplace el original y regenere la copia con el mismo
  alto.
- Impresión: tablas anchas sin recorte (8 pt), sin flechas de ordenar, leyendas de gráficos en SVG
  (Chrome omite los fondos por omisión). `capturar.py --pdf` guarda el PDF como lo imprime Chrome.
- Pendiente del punto 8: inicio de sesión UMSA (según el proveedor que confirme la DTIC) y Guía de
  Antecedentes de IAC-CINDA (falta la planilla oficial vigente).

## 36. Guía de Antecedentes de IAC-CINDA (punto 8 de la evaluación, 28-sep-2026)

- La Dirección entregó la planilla oficial vacía (pregrado, 2025): 33 hojas, 9 gráficos en el resumen
  estadístico. Se versiona en `datos/iac-cinda/` (decisión del 28-sep-2026); los PDF siguen fuera.
- `app/comun/xlsx_plantilla.py` escribe celdas en el XML de cada hoja con lxml y deja intacto lo demás
  (openpyxl descarta gráficos e imágenes al guardar). Filas agregadas más allá de la tabla toman el
  formato de su última fila numerada; si se sobrescribe la maestra de una fórmula compartida, las
  dependientes pasan a fórmula explícita; se pide recalcular al abrir y se quita la cadena de cálculo.
- `app/acreditacion/guia_antecedentes.py` llena las hojas 1, 2, 7.a, 7.b, 10, 11, 12, 19–23, 25–27;
  `COBERTURA` dice qué queda a mano. Pantalla y descarga en `/informes/guia-antecedentes`
  (`ver_informes_institucionales`, sin unidad: Direcciones de Carrera e Instituto y Comité).
- Decisiones del 28-sep-2026: horas en **h/semana** (h/mes ÷ 4); jornada completa ≥ 160 h/mes, media
  80–159, por horas < 80 (sin carga registrada cuenta como por horas y se anota); montos en USD con el
  **tipo de cambio que indica quien genera la guía**.
- Decisiones confirmadas por la Dirección (1-oct-2026):
  - «Académicos del programa»: vínculo con la Carrera como titular, contratado(a), interino(a) o
    invitado(a) (no «externo»); la hoja 10 los toma al cierre del último año (o a hoy).
  - Hoja 20: proyectos individuales e institucionales de investigación; los de interacción social van
    a la 27 (extensión) con las actividades de divulgación. Monto de un institucional → financiamiento
    interno; de un individual → externo, con su fuente.
  - Hojas 22, 23 y 25: productos enviados, aceptados o publicados en los años de los 10 ciclos con al
    menos un autor del programa vinculado en la fecha (sin exigir revista verificada ni arbitraje).
  - 7.a: «veces que se dicta» = gestiones del último año en que se ofertó. El **cupo por sección** y la
    **duración del programa** (hoja 1) quedan en blanco para completarlos a mano con el dato oficial.
- Errores de la plantilla que se corrigen en el archivo generado: tasas de egreso y titulación (hojas
  5 y 6) apuntaban a otro libro (`[1]4.b.Cohortes semestre-ciclo`); deserción al tercer año de la
  cohorte de la fila 18 (hoja 4) usaba la fila 17; «Costo total» de la hoja 20 sumaba AQ+AR (columnas
  de difusión) en vez de AT+AU. Se quita el vínculo externo.
- Pendiente del punto 8: inicio de sesión UMSA (proveedor por confirmar con la DTIC).

## 37. Etapas de propuestas, botones que esperan y barras de avance (1-oct-2026)

- `app/comun/componentes/etapas.py`: indicador de etapas propio (lista ordenada con Tailwind, sin
  JavaScript, `aria-current="step"`, texto para lectores de pantalla; versión compacta para listas).
  No se usa `Steps` de MonsterUI porque depende de daisyUI, que TAU no carga.
- Propuestas: `institucionales.pasos(prop)` arma preparación → envío (o reenvío) → decisión → proyecto,
  con las fechas del historial; en la ficha y, compacto, en «Mis propuestas institucionales».
  `requisitos(prop)` da cada requisito para enviar y si se cumple (`faltantes` sale de ahí); el
  editor muestra «Requisitos para enviar: x de n» con `Progress`.
- `boton_espera` (layout): se deshabilita y gira durante la petición HTMX. En enviar propuesta,
  registrar decisión, actualizar citas, buscar en OpenAlex e importar por DOI/arXiv. Reemplaza a
  `LoaderButton` de MonsterUI, que no aplana clases en tupla.
- «Mi docencia» (y la ficha del docente): barras de docencia asignada frente a prevista y de horas
  asignadas en proyectos frente a la investigación o extensión del vínculo.
- Decisión confirmada por la Dirección (1-oct-2026): en la lista de la Dirección del Instituto queda solo la
  insignia de estado (la tabla ya tiene la fecha de envío); el indicador compacto va en «Mis
  propuestas». La preparación del semestre queda para una etapa posterior.
- `capturar.py --base RUTA` para capturar con una base preparada.

## 38. Preparación del semestre (1-oct-2026)

- `app/academico/preparacion.py`: `estado(anio, tipo)` con cinco etapas (gestión creada → oferta
  cargada → contratos renovados → docentes asignados → carga cuadrada), cada una con su detalle, lo
  que falta en una frase, avance (x de n) y pendientes. Reutiliza las reglas de oferta,
  `carga.candidatos_renovacion` y `carga.personas` (avisos de carga), sin duplicarlas.
- Pantalla `/docencia/preparacion` (pestaña «Preparación del semestre»; Dirección de Carrera y
  Coordinación académica): indicador de etapas con enlaces, tarjetas con barra de avance, pendientes
  y acceso a donde se resuelve cada etapa (si el rol no puede, dice quién lo hace). Inicio: «Preparación
  de I-2027: x de 5 etapas listas · Siguiente: …».
- Decisiones confirmadas por la Dirección (1-oct-2026): por omisión se prepara el **próximo semestre que no empezó**
  (con las fechas de su gestión o, si no existe, las de omisión); las troncales que no se ofertan se
  muestran como dato pero no impiden dar la oferta por cargada (la Dirección puede quitar una a
  propósito); sin gestión, las demás etapas quedan a la espera; los cursos de verano e invierno no
  entran.

## 39. Informes programados (1-oct-2026)

- Decisiones de la Dirección (1-oct-2026): se envían solos la **preparación del semestre** (4 y 1
  semana antes del inicio, a la Dirección de Carrera y la Coordinación académica), la **carga docente**
  (al inicio de cada semestre, a la Dirección de Carrera), la **memoria anual** (desde el 10 de enero,
  a la Dirección del Instituto) y la **calidad de datos** (mensual, a quienes ven el tablero). Cada
  correo lleva **cifras clave y el enlace** (sin adjuntos: los datos personales no salen del sistema),
  en **fechas fijas** y a quienes tienen el **rol** en ese momento.
- `app/acreditacion/programados.py`: `pendientes_de_hoy`, `revisar(hoy)` (envía como aviso con
  `notificaciones.avisar`: campana y correo según la preferencia de cada persona), `proximos`, `suyos`.
  Se revisa a lo más una vez por hora con el mantenimiento de `main.py`; `PORTAL_INFORMES_PROGRAMADOS=0`
  lo apaga (las pruebas lo hacen y llaman a `revisar` con la fecha que necesitan).
- Migración 0037: tabla `informe_programado` (informe, ocasión, fecha, destinatarios) para que cada
  envío salga una sola vez.
- «Informes» muestra a cada persona los informes que recibe: próximos envíos y últimos realizados.
- Decisiones confirmadas por la Dirección (1-oct-2026):
  - Ventanas: la memoria se envía entre el 10 de enero y el 31 de marzo; la carga, en las 3 semanas
    siguientes al inicio; si en la ventana nadie usa el sistema, ese envío no ocurre (no hay tareas
    programadas en el servidor).
  - Calidad de datos: si no hay nada que corregir, no se envía (se registra para no reintentar).
  - Sin nadie con el rol, el envío no se registra y se reintenta en la siguiente revisión.
  - Los cursos de verano e invierno no generan informes.

## 40. Premios, arbitraje y prestación de servicios (1-oct-2026)

- Decisiones de la Dirección (1-oct-2026): se registran **como tipos de actividad** («Premio o
  distinción», «Arbitraje de artículos», «Prestación de servicios»); el arbitraje, **por revista y año**
  con la cantidad de artículos; los servicios los registran **quienes los realizan**, con **monto,
  moneda, origen del financiamiento (interno o externo) e ingresos** para la unidad.
- Migración 0038: los tres tipos; columnas `cantidad`, `revista_id`, `monto`, `moneda`,
  `financiamiento` e `ingresos` en `actividad`; roles nuevos de participante (`distinguido`, `revisor`,
  `responsable`, con la tabla reconstruida para cambiar el CHECK).
- Formulario: el bloque de fechas, institución y campos propios se pide al servidor al cambiar el tipo
  (`/actividades/campos`, conserva lo escrito). El arbitraje guarda del 1 de enero al 31 de diciembre
  del año (se muestra «2026») y reconoce la revista del catálogo por su título. Cada tipo exige al
  menos un participante con su rol.
- Anexo: «Reconocimiento de pares» (2.2.1 d) con premios, arbitraje y comités; sección nueva 3.4.3;
  tres indicadores con trazabilidad (los arbitrajes suman artículos: `anexo.SUMAS`); el XLSX los trae
  con cantidad y montos. Ya no figuran en «Aún no registrado» (queda el impacto de la vinculación).
- Guía de Antecedentes: hoja 10, columna de logros (premios en los años de la guía); hoja 28 completa
  salvo impacto, evaluación y difusión.
- Decisiones confirmadas por la Dirección (1-oct-2026):
  - Un arbitraje cuenta en la memoria si el revisor estaba vinculado el 1 de enero de ese año (la regla
    general usa la fecha de inicio de la actividad).
  - Un servicio sin origen del financiamiento se pone como externo en la Guía (y se anota).

## 41. Fusionar coautores externos duplicados (1-oct-2026)

- `personas.posibles_duplicados()`: pares de externos sin cuenta con el mismo ORCID, o con el mismo
  apellido (sin tildes ni mayúsculas) y nombres compatibles en orden (iguales, o uno es la inicial del
  otro: «H.» y «Hermann»). Dos ORCID distintos nunca se proponen; un «H.» ambiguo se propone con
  cada candidato y decide una persona.
- `personas.fusionar(conservar, eliminar)`: en una transacción, pasa autorías, participaciones en
  actividades y proyectos y periodos de estudiante (si ambas fichas estaban en el mismo registro,
  queda una), completa institución, país, ORCID y correo faltantes y borra la otra ficha. Sin
  migración. Se audita (`fusionar_externos`).
- Pantalla `/personas/externos/duplicados` (acción `gestionar_personas_externas`: Dirección del
  Instituto y Gestión de datos; las investigadoras e investigadores no fusionan, porque afecta
  registros ajenos). Tablero de calidad: revisión «Coautores externos posiblemente duplicados».
- Decisiones confirmadas por la Dirección (1-oct-2026):
  - Quién fusiona: Dirección del Instituto y Gestión de datos (no cada investigador).
  - En un proyecto en que estaban ambas fichas, se conservan el rol y las fechas de la ficha elegida.
- El mismo punto del plan original incluía vincular una persona externa a su cuenta: ver §42.

## 42. Vincular una persona externa a su cuenta (1-oct-2026)

- Decisiones de la Dirección (1-oct-2026): si tiene periodos de estudiante, la ficha externa se
  **conserva enlazada** a la cuenta (`persona_externa.usuario_id`) solo para guardarlos; vinculan la
  **Dirección del Instituto y Gestión de datos**; el sistema **sugiere** los pares y una persona confirma.
- `personas.sugerencias_de_cuenta()`: externos sin cuenta vinculada con el mismo ORCID, correo, o apellido
  y nombres compatibles que una cuenta activa (nunca con ORCID distintos).
- `personas.vincular_a_cuenta(externo, usuario)`: en una transacción, autorías y participaciones en
  actividades y proyectos pasan a la cuenta (sin repetir en un mismo registro; la filiación de esas
  autorías queda sin declarar); el ORCID pasa al perfil si no lo tiene; la ficha se conserva enlazada
  si tiene periodos de estudiante y, si no, se borra. Se audita (`vincular_externo`). Sin migración.
- `estudiantes.ficha(p)`, `estudiante_de(p, anio)`, `graduado_de(p, anio)`: la condición de estudiante de
  cualquier persona (externa o con cuenta, por su ficha enlazada). Las usan los indicadores de
  estudiantes (tesis, productos, proyectos y actividades con estudiantes) y la Guía, para que lo que
  alguien hizo como estudiante siga contando tras recibir cuenta.
- Pantalla: `/personas/externos/duplicados` («Duplicados y cuentas») con la sección «Ya tienen cuenta»;
  vinculación manual desde la lista de externos. Tablero de calidad: «Coautores externos que ya tienen
  cuenta».

## 43. Política de seguridad de contenido estricta (2-oct-2026)

- `script-src 'self'`: sin 'unsafe-inline' ni 'unsafe-eval'. Los estilos siguen admitiendo
  'unsafe-inline' (atributos `style=` de Franken UI, htmx y los gráficos SVG; no ejecutan código).
- Unos 60 manejadores en el HTML (`onclick`, `onchange`, `onsubmit`, `onkeydown`, `hx-on`) pasaron a
  atributos `data-*` que atiende `static/js/acciones.js` por delegación (modal, filas, buscadores,
  copiar, imprimir, selects que navegan, pestañas). El modal se cierra con Escape o con un clic fuera
  del cuadro (`data-fondo-modal`); la constante `JS_CERRAR` se reemplazó por `CERRAR`.
- Scripts en línea a archivos: tema inicial (`static/js/tema-inicial.js`, el de `headers_theme` de
  MonsterUI), KaTeX (`static/js/katex.mjs`), errores de HTMX y avisos (`static/js/avisos.js`). Los avisos
  de `add_toast` se sirven sin `hx-on` (`avisos_emergentes.py`, en lugar de `setup_toasts`).
- htmx con `allowEval: false`. `tests/test_csp.py`: cabecera estricta, páginas y modales sin código en
  línea, ninguna línea con manejadores en `app/`, tema inicial igual al de MonsterUI. Pruebas en
  navegador del modal, las filas, los avisos y los selectores (fallan con cualquier violación).
- De paso: «Nueva actividad» daba error 500 a una cuenta sin perfil de investigador; ahora empieza sin
  participantes.

## 44. División de los archivos de rutas más grandes (2-oct-2026)

- `app/investigacion/rutas/productos/formulario.py` (484 líneas) se dividió por flujo, sin cambiar
  comportamiento: `campos.py` (revista del catálogo, revisión, índices y actividad que dependen del
  tipo; `/productos/campos` y `/productos/revistas`), `formulario.py` (formulario, recuadro de
  importación, alta, edición y eliminación) e `importar.py` (DOI o arXiv, aviso de duplicado y
  «Sumarme como autor»). La insignia de estado de la revista pasó a `ficha.py`, su único uso.
- Verificado: las mismas 270 rutas antes y después, sin ciclos entre módulos, suite completa con
  navegador (529).
- Lo mismo con `app/comun/rutas/admin_usuarios.py` (1.111 líneas), ahora un paquete: `comun` (fila de
  la tabla, `gestiona_vinculos`, `SIN_PERMISO`), `cuentas`, `importar_cuentas`, `roles`, `ficha`,
  `vinculo` e `historial`. `fecha_local`, que usaban otros cinco módulos, pasó a
  `app/comun/componentes/registros.py`. Mismas 270 rutas y en el mismo orden; suite completa (529).

## 45. Clasificación MSC2020 de los productos (2-oct-2026)

**Decisiones de la Dirección (2-oct-2026):**
- Como en las revistas y en zbMATH: un código **principal** y hasta **4 secundarios**, de cualquier
  nivel del catálogo (11-XX, 11Mxx, 11M06). Los informes agrupan por la sección (dos primeros
  caracteres) del principal.
- Sugerencia al registrar: al importar por DOI se consulta **zbMATH Open** (servicio público y
  gratuito) y se traen sus códigos; si no los hay, el área principal del perfil de los autores. Siempre
  editable.
- Se usa en la ficha, el perfil público y la API; como filtro de «Mis productos»; en la memoria
  (producción por área, con gráfico) y en Calidad de datos (aviso, sin volverla obligatoria).

**Implementación:**
- Migración 0039: tabla `producto_msc(producto_id, codigo, orden)`; el principal es el de orden 0.
  Los productos existentes quedan sin clasificar (el seed clasifica los de ejemplo).
- `app/investigacion/msc.py`: `de_producto`, `validar`, `guardar_de_producto`, `sugeridos_por_perfil`.
  `productos.preparar` valida `msc` solo si viene en los datos: BibTeX, OpenAlex y otras vías que no la
  traen no borran la que había.
- Formulario: selector ordenable (`app/investigacion/componentes/msc.py`, compartido con el buscador
  del perfil); la marca «Principal» la lleva por CSS el primero de la lista, así se actualiza al
  reordenar sin ir al servidor. Rutas `/productos/msc/buscar` y `/productos/msc/fila`.
- `importacion.msc_de_zbmath(doi)`: `api.zbmath.org/v1/document/_structured_search?DOI=…` (el primer
  código de zbMATH es el principal). Si falla o no responde, devuelve [] sin estorbar la importación.
  Para un preprint sin DOI se usa el DOI de su versión publicada, si arXiv lo informa.
- Memoria: «Por área (MSC2020)» (tabla y gráfico, indexados y arbitrados, y «sin clasificar»); el XLSX
  de productos suma la columna «MSC2020 (principal primero)». Calidad de datos: «Publicaciones
  indexadas o arbitradas sin clasificación MSC2020» en la ventana del anexo.
- API `/api/v1/productos`: campo `msc` (código, texto, principal). Perfil público: códigos bajo cada cita.

**Decisiones confirmadas por la Dirección (2-oct-2026):**
- El filtro por área de «Mis productos» cuenta el código principal **y** los secundarios (la memoria
  cuenta solo el principal, para no contar un producto dos veces).
- En un producto nuevo (sin importar) se sugiere el área principal del perfil de quien registra.
- La cosecha desde OpenAlex y la importación BibTeX no consultan zbMATH: esos productos quedan sin
  clasificar y aparecen en Calidad de datos.
- El aviso de Calidad de datos abarca las publicaciones indexadas o arbitradas, aceptadas o publicadas,
  con algún autor del instituto, en la ventana del anexo (no solo las que cuentan en la memoria).

## 46. Preprint y versión publicada (2-oct-2026)

**Decisiones de la Dirección (2-oct-2026):**
- Con el preprint enlazado a su versión publicada, el CV, el perfil público y la exportación BibTeX
  listan **solo la versión publicada**, con un enlace a su arXiv. El preprint sigue en «Mis productos»,
  marcado «Con versión publicada».
- Al importar la versión publicada de un preprint **ya registrado** se crea un **registro nuevo
  enlazado**; el preprint se conserva y se preseleccionan sus proyectos.
- Los artículos que ya guardan su arXiv en el mismo registro (importados como versión publicada de un
  preprint no registrado) **quedan así**; ese caso sigue igual.

**Implementación:**
- Migración 0040: `producto.publicado_como_id` (en el preprint, hacia su versión publicada; ON DELETE
  SET NULL) con índice único: una versión publicada tiene a lo sumo un preprint.
- `productos`: `obtener` agrega `publicado_como` (en el preprint) y `preprint` (en la versión);
  `arxiv_de(p)` da el arXiv propio o el del preprint; `enlazar_version`/`desenlazar_version`;
  `sin_preprints_publicados(lista)` quita un preprint solo si su versión está en la misma lista (en un CV
  de un periodo que no la incluye, el preprint sí aparece); `candidatos_version` ordena por parecido de
  título (difflib); `preprints_sin_enlazar` para Calidad de datos (mismo autor del instituto, títulos con
  parecido ≥ 0,85). Si un producto cambia de tipo, su enlace se quita.
- Se aplica en el CV (y su BibTeX), «Exportar BibTeX» de «Mis productos», el perfil público y la API
  `/api/v1/productos`. La memoria y el anexo no cambian: los preprints no cuentan.
- Rutas `/productos/{pid}/version` (GET ventana, POST enlazar, DELETE desenlazar) en
  `rutas/productos/version.py`; `/productos/importar` acepta `preprint` y reconoce el arXiv registrado
  en `arxiv_asociado`. Seed: un preprint de Emmy enlazado a su artículo.

**Decisiones confirmadas por la Dirección (2-oct-2026):**
- No pueden ser versión publicada: preprints, presentaciones, tesis dirigidas ni patentes.
- Enlazar exige poder editar ambos productos (ser autor o haberlos registrado); un preprint ajeno no se
  enlaza al importar (se ofrece «Sumarme como autor», como hoy).
- La API pública aplica la misma regla que el perfil público.
- El aviso de Calidad de datos sugiere pares con un autor del instituto en común, títulos muy parecidos y
  la versión del año anterior al preprint o posterior.

## 47. Catálogos desde la interfaz (2-oct-2026)

**Decisiones de la Dirección (2-oct-2026):**
- Los tipos y los índices que ya existían son **del sistema**: se reordenan y se activan o desactivan;
  su nombre queda fijo, porque el anexo, la Guía de Antecedentes, el CV y las importaciones los reconocen
  por él (84 lugares del código).
- Un tipo **nuevo** cuenta de forma genérica: formularios, listas, CV y memoria (los productos, según su
  nivel de revisión); no entra en las categorías del anexo ni de la Guía.
- En **cualquier índice** se puede cambiar si cuenta como «indexado» o «arbitrado», con aviso y auditoría.
- Los administra la **Dirección del Instituto** (permiso «gestionar catálogos», como revistas y líneas).

**Implementación:**
- Migración 0041: columna `del_sistema` en `tipo_actividad`, `tipo_producto` e `indice`, en 1 para todo
  lo existente.
- `app/investigacion/catalogos.py` (listar con uso, validar nombre único sin distinguir tildes ni
  mayúsculas, crear, actualizar, activar, mover, eliminar solo lo agregado y sin uso,
  `reclasificar_indice`) y la pantalla `/admin/catalogos` («Tipos e índices» en el menú).
- Al cambiar la política de un índice, el nivel de revisión guardado en los artículos de las revistas
  verificadas que figuran en él se recalcula con `revistas.reclasificar`; los de revistas sin verificar
  conservan lo declarado por sus autores. La auditoría registra el cambio y cuántos artículos cambiaron.
- Desactivar no rompe lo registrado: al editar, el formulario ofrece el tipo o los índices que el registro
  ya tenía (`tipos(incluir=…)`, `indices(incluir=…)`) y la validación los acepta; un registro nuevo con un
  tipo desactivado (p. ej., uno importado) recibe «El tipo … está desactivado: elija otro». Los filtros de
  las listas ofrecen también los inactivos.

**Decisiones del equipo (confirmar):**
- Un tipo o índice nuevo se agrega al final del orden y activo.
- Un tipo de producto nuevo pregunta solo si «puede ser indexado o arbitrado»; uno de actividad, solo el
  nombre (usa los campos generales del formulario).
- En los tipos del sistema no se puede cambiar «puede ser indexado o arbitrado»: es parte de las reglas del
  CV y la memoria.

## 48. Valoración de usabilidad y buenas prácticas (3-oct-2026)

Valoración del stack y de la experiencia de uso, con mediciones sobre una base ampliada a unos 3.000
productos y capturas en pantalla de teléfono (sin usuarios reales ni auditoría con lector de pantalla).
Veredicto: el stack es adecuado; los problemas son de terminación y escala. Orden acordado:

1. **Hecho (3-oct-2026):** fila de autores en el teléfono y «Cargar más» en las listas largas.
2. **Hecho (3-oct-2026):** accesibilidad del modal (foco, `aria-labelledby`, enlace «Saltar al
   contenido»), foco en el resumen de errores y botones que se desactivan mientras se envía.
3. **Hecho (4-oct-2026):** registros de actividad y de errores (requisito del despliegue).
4. **Hecho (4-oct-2026):** búsqueda global y confirmaciones propias con «Deshacer» en lo reversible.
5. **Hecho (4-oct-2026):** «Avisar a los responsables» desde Calidad de datos y exportar la auditoría en CSV.
6. Deuda técnica: armar productos en lote (N+1), modelo de formulario compartido para alta y edición,
   `ruff` y `pyright`.

Además, antes de la puesta en marcha: prueba de usabilidad con cinco personas reales y cinco tareas.

**Paso 1, implementación y mediciones:**
- Fila de autores y participantes (`componentes/personas.py`): en pantallas chicas el selector de
  filiación o de rol baja a su propia línea; antes tapaba el nombre y cortaba los botones.
- «Cargar más» de 50 en 50 (`registros.cargar_mas`, rutas `/productos/mas` y `/actividades/mas`, con los
  mismos filtros). `productos.buscar` devuelve solo id, año, revisión y estado; el producto completo se
  arma solo para lo que se muestra. Lo usan también el inicio, la ficha del investigador (15 productos) y
  el CV (que filtra por periodo antes de armar).
- Con 3.000 productos: «Mis productos» de 1,8 s y 5,9 MB a 20 ms y 109 KB; el inicio de 196 ms a 5 ms.
- La lista de usuarios no se pagina: con 300 cuentas responde en unos 100 ms (726 KB), y su tabla
  ordena, filtra y exporta en el navegador, lo que con páginas abarcaría solo lo cargado.

**Paso 2, implementación:**
- `pagina()`: enlace «Saltar al contenido» (visible al recibir el foco con Tab) hacia `<main id="contenido">`.
- `modal()`: `aria-labelledby` con su título. `acciones.js`: el foco entra en el primer campo al abrirlo,
  Tab y Mayús+Tab recorren solo el cuadro y, al cerrarlo (botón, Escape, clic fuera o el servidor al
  guardar), el foco vuelve al elemento que lo abrió.
- `mensaje_error()`: `tabindex="-1"` y `data-resumen-errores`; al llegar en una respuesta recibe el foco y el
  lector de pantalla lo anuncia (`role="alert"`). Asociar cada error a su campo (`aria-describedby`,
  `aria-invalid`) exigiría que las validaciones devuelvan el campo además del texto: queda para después.
- Envíos: mientras dura una petición que no es GET, su botón o los de envío del formulario quedan
  deshabilitados. Corrección a la valoración: htmx ya encola un segundo envío del mismo formulario y lo
  descarta si la respuesta lo reemplaza o cierra el modal, así que el riesgo de envío doble era menor de lo
  dicho (solo en formularios que siguen en pantalla). Lo principal es la señal de que se está guardando.
- La prueba en navegador falla sin el cambio de los envíos (comprobado quitándolo).

**Paso 3, implementación (`app/comun/registros.py`):**
- Middleware ASGI con una línea por petición (método, ruta, código, ms, id del usuario); WARNING si tarda
  1 s o más. Sin la consulta ni el cuerpo, y con los tokens de `/recuperar/…` ocultos. Sin `/static` ni
  `/salud`. A consola y a `data/registros/portal.log` (10 MB × 5).
- Error no controlado: traza con un código de referencia de 6 caracteres; página «Error del sistema» con
  el código (antes, el texto plano de Starlette) y, en HTMX, la cabecera `X-Referencia` que el aviso muestra.
  `PORTAL_AVISO_ERRORES`: correo a la administración, a lo más uno cada 15 minutos.
- `GET /salud` (pública, comprueba la base) para el chequeo del hosting; `fly.toml` pasa de `/login` a
  `/salud`. uvicorn arranca con `--no-access-log`.

**Decisiones del equipo (confirmar):**
- No se registra la consulta de las búsquedas (`?q=…`) ni el contenido de los formularios: puede traer
  nombres o datos personales. Se registra el id del usuario, no su correo.
- Los registros se guardan junto a la base y rotan (unos 60 MB como máximo); no se envían a servicios
  externos.
- El aviso por correo de errores es opcional y se limita a uno cada 15 minutos.

**Paso 4, implementación:**
- Búsqueda global (`app/busqueda.py`, rutas `/buscar/sugerencias` y `/buscar`): campo en la barra (desde
  1280 px; más angosto, una lupa que lleva a /buscar), tecla «/», Escape y clic fuera cierran las
  sugerencias. Grupos: personas (directorio), cuentas que no son de investigadores (solo con
  «ver_usuarios»), productos (título, DOI o arXiv), actividades, proyectos (solo los que `puede_ver`) y
  asignaturas (llevan a su fila, resaltada, en el plan más reciente que la incluye).
- Confirmaciones: `htmx:confirm` abre un `<dialog>` nativo (foco retenido, Escape cancela) en lugar de
  `confirm()`. El botón toma el verbo de la pregunta («Eliminar», «Quitar»…; «Continuar» si no lo hay), es
  rojo si la acción destruye algo y, entonces, el foco empieza en «Cancelar». Sin cambios en las 35
  preguntas existentes.
- «Deshacer» (`aviso_con_deshacer`): en lugar de confirmar, en desactivar un tipo o índice, desactivar
  una cuenta sin terminar su vínculo y desenlazar un preprint. Las rutas aceptan el estado explícito
  (`activo=0|1`), así que deshacer dos veces no revierte el deshacer.

**Decisiones del equipo (confirmar):**
- Qué se busca y quién: lo de arriba. No se buscan las revistas del catálogo, las líneas ni los avisos.
- Solo esas tres acciones pasan a «Deshacer»; el resto sigue pidiendo confirmación (no se pueden revertir
  con lo que hay, o revertirlas no deja todo igual, como quitar un rol o dar de baja a un participante).
- El aviso con «Deshacer» dura 10 segundos.

**Paso 5, implementación:**
- Calidad de datos: cada ítem sabe a quién corresponde (`para`): la persona (sin grado, perfil
  incompleto), los autores del instituto (publicaciones por confirmar, sin MSC, preprints sin enlazar) o
  los responsables (proyectos sin ámbito o sin línea). `calidad.avisar(clave, por)` envía a cada uno, por el
  centro de avisos, la lista de lo suyo (hasta 10, y «… y N más»), con enlace al registro si es uno solo o a
  su página («Mi perfil», «Mis productos», «Proyectos»). No se repite a quien recibió el mismo aviso en los
  últimos 7 días (se consulta `notificacion`; sin tabla nueva). Botón «Avisar a N personas», con
  confirmación; queda en la auditoría.
- Auditoría: filtros por fechas (incluyen ambos días; sobre la fecha UTC del registro) y «Descargar CSV» con
  todo lo filtrado (UTF-8 con BOM, fórmulas neutralizadas, encabezado aunque no haya filas); la exportación
  se audita. La exportación a CSV y XLSX pasa a `app/comun/exportar.py` (la usan los informes y la auditoría).

**Decisiones del equipo (confirmar):**
- Avisan las direcciones (Instituto y Carrera) y la Coordinación académica (permiso nuevo «avisar_calidad»).
  El Comité de acreditación solo mira y Administración del sistema no decide sobre contenido.
- Lo que corrigen las direcciones o la administración (vínculos, fecha de nacimiento, oferta, planes,
  coautores externos) no tiene «Avisar»: lo ve quien lo corrige.
- Un aviso por revisión y persona cada 7 días como máximo.
