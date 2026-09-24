# Portal de Investigación: diseño y estado

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
| **Administración** | Indicador `es_admin` de la cuenta | Crea cuentas (una a una, por CSV o con invitación), activa, desactiva, desbloquea y restablece; crea proyectos y asigna responsables; ve la memoria anual, la auditoría y el CV de cualquier investigador |
| **Investigador(a)** | La cuenta tiene fila en `investigador` | Edita su perfil; registra actividades y productos; participa en proyectos; genera su CV |
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
- Siempre queda al menos un responsable vigente. Solo la administración asigna o quita
  responsables; las personas externas no pueden serlo.
- Solo participantes vigentes proponen, y solo a proyectos no finalizados.
- El responsable de una actividad debe ser participante del mismo proyecto.
- Ven el proyecto sus participantes (actuales o anteriores) y la administración.

**Cuentas y acceso**
- Contraseñas con Argon2; mínimo 10 caracteres combinando letras con números o símbolos.
- Contraseña temporal → cambio obligatorio en el primer ingreso.
- 5 intentos fallidos en 15 minutos bloquean el ingreso (la administración puede desbloquear).
- Enlaces de recuperación e invitación de un solo uso (1 hora / 3 días); se guarda solo su hash.

## 5. Modelo de datos

Esquema vigente (migraciones `0001` a `0007` en `migrations/`):

```
usuario(id, email, nombres, apellidos, pass_hash, es_admin, activo, debe_cambiar_pass,
        creado_en, ultimo_acceso, avisos_correo)
investigador(usuario_id, grado, cargo, unidad, orcid, mr_id, zbmath_id, arxiv_id, scholar_url,
             pagina_web, bio, foto, perfil_publico, actualizado_en)
investigador_msc(usuario_id, codigo, principal, orden)
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
indice(id, nombre, cuenta_como_indexado, orden, activo)
producto(id, tipo_id, titulo, anio, estado_publicacion, revision, medio, volumen, numero,
         paginas, doi, arxiv_id, url, resumen, actividad_id, creado_por, creado_en, actualizado_en)
producto_autor(producto_id, orden, investigador_id | externo_id)
producto_indice(producto_id, indice_id)
adjunto(id, entidad, entidad_id, nombre, archivo, mime, tamano, subido_por, subido_en)

proyecto(id, codigo, nombre, descripcion, objetivo_general, fuente_financiamiento, monto,
         moneda, fecha_inicio, fecha_fin, estado, creado_por, creado_en, actualizado_en)
proyecto_objetivo(id, proyecto_id, orden, texto)
proyecto_participante(id, proyecto_id, investigador_id | externo_id, rol, fecha_desde, fecha_hasta)
actividad_proyecto(actividad_id, proyecto_id, estado, responsable_participante_id,
                   propuesto_por, propuesto_en, revisado_por, revisado_en, comentario)
producto_proyecto(producto_id, proyecto_id, estado, propuesto_por, propuesto_en,
                  revisado_por, revisado_en, comentario)
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

**Despliegue:** servidor propio (systemd + Caddy) o Fly.io (contenedor, volumen y réplica
continua de la base con Litestream). El paquete de datos (`scripts/paquete.py`) y el modo solo
lectura permiten mudarse entre ambos sin perder información.

200 pruebas automáticas. El detalle de cada entrega está en el historial de git (un commit por fase).

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
- Si se usa Fly.io: construir la imagen (`docker build .`) y probar un despliegue real. El
  arranque con Litestream (restauración tras perder el volumen) se probó localmente; la imagen de
  Docker y la plataforma, todavía no.

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
