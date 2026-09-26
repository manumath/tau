# Guía de uso del Portal de Investigación

El portal reúne la actividad científica del instituto: cada persona registra sus productos y
actividades **una sola vez**, y con eso se generan su CV, los informes de los proyectos y la
memoria anual.

- [Ingreso y contraseña](#ingreso-y-contraseña)
- [Mi perfil](#mi-perfil)
- [Productos](#productos)
- [Actividades](#actividades)
- [Proyectos](#proyectos)
- [Informes](#informes)
- [Administración](#administración)
- [Preguntas frecuentes](#preguntas-frecuentes)

## Ingreso y contraseña

- Ingrese con su correo institucional. Si recibió una **invitación por correo**, abra el enlace
  (vale 3 días) y defina su contraseña. Si le entregaron una **contraseña temporal**, el portal
  le pedirá cambiarla al primer ingreso.
- La contraseña debe tener al menos 10 caracteres y combinar letras con números o símbolos.
- **¿La olvidó?** Use «¿Olvidó su contraseña?» en la pantalla de ingreso: recibirá un enlace
  válido por una hora.
- Tras 5 intentos fallidos el ingreso se bloquea 15 minutos. La administración puede
  desbloquearlo antes.
- Para cambiar su contraseña: menú con su nombre (arriba a la derecha) → «Cambiar contraseña».

## Mi perfil

Menú con su nombre → «Mi perfil». Cada sección se edita con su botón «Editar».

- **Datos básicos:** grado, cargo y unidad o grupo.
- **Identificadores:** ORCID, MathSciNet, zbMATH, arXiv, Google Scholar y página web. Puede pegar
  la dirección de su perfil: el portal guarda solo el identificador y verifica el ORCID.
- **Áreas de investigación:** escriba un código MSC2020 (`11M`) o un tema en inglés (`zeta`,
  `graph coloring`) y elija de la lista. La marcada con ★ es su área principal.
- **Resumen de investigación:** admite fórmulas en LaTeX (`$\zeta(s)$`, `$$…$$`), con vista previa.
- **Foto:** JPG, PNG o WebP hasta 5 MB; se recorta en un cuadrado.
- **Privacidad y avisos:**
  - *Perfil público*: publica su perfil y sus publicaciones en la web del portal (sin correo,
    actividades ni proyectos). Está desactivado hasta que usted lo active.
  - *Avisos por correo*: sobre propuestas en proyectos que usted dirige y sobre la revisión de
    las suyas.

El indicador «Perfil completo» muestra qué falta. Los demás investigadores ven su perfil en
«Investigadores», el directorio interno, que se puede filtrar por categoría.

Su **vínculo** con el instituto (desde cuándo y con qué categoría: titular, contratado(a),
interino(a), invitado(a) o externo(a)) figura en «Datos básicos». Lo registra la administración
con los datos de Recursos Humanos: si no es correcto, pídale que lo corrija. Puede registrar
también su producción anterior al ingreso: aparece en su perfil y su CV, pero no en los informes
institucionales.

## Productos

«Productos» lista los artículos, libros, reportes, presentaciones y demás de los que usted es
autor(a) o que registró. Los filtros (texto, año, tipo, «solo los que cuentan para el informe»)
quedan en la dirección de la página, para volver a ellos o compartirlos.

### Estudiantes y tesistas

En **Investigadores → Estudiantes y tesistas** registre a los estudiantes que participan en su
investigación: tesistas, coautores, participantes de proyectos o actividades. Para cada uno indique
sus estudios (nivel, programa, año de ingreso y, si ya egresó, año de egreso y si se tituló). Así los
informes de acreditación cuentan su participación, y el portal sabe si alguien era estudiante o ya
graduado en la fecha de cada producto.

Registre las **tesis que dirige** como producto «Tesis dirigida»: primero el tesista y luego quienes
la dirigen; «En preparación» si está en curso y «Publicado» cuando se defendió.

### Buscar su producción en OpenAlex

**«Buscar en OpenAlex»** (en «Mis productos») usa el ORCID de su perfil para encontrar sus obras en
OpenAlex, un catálogo abierto de publicaciones. Muestra cuáles son nuevas, cuáles ya están en el
portal y cuáles no se importan (p. ej., su tesis doctoral). Marque las que quiere registrar y
presione **«Registrar las seleccionadas»**: se crean con sus coautores, la revista del catálogo (o
propuesta, si no está), la filiación IIMAT/UMSA si la afiliación publicada la menciona, y sus citas.
**Revise cada obra**: OpenAlex a veces atribuye obras por error. «Descartar» oculta una obra que no
es suya en las próximas búsquedas. Por omisión se buscan los últimos 5 años.

### Registrar un producto

El **mes de publicación** es opcional, pero conviene indicarlo: sin él, un producto no se puede
ubicar en los informes por periodo octubre–septiembre (queda «por confirmar»).

**Revista (artículos en revista):** busque la revista en el **catálogo del instituto** por título
o ISSN. Si la revista está **verificada**, el nivel de revisión y los índices se toman del catálogo
según el año de publicación (no se declaran). Si no está en el catálogo, «Propóngala» con su título
e ISSN: quedará pendiente hasta que la administración la verifique, y mientras tanto rige lo que
usted declare. Al importar por DOI, la revista se reconoce sola por su ISSN.

**Otros resultados:** registre también **patentes** (oficina en «medio», número en «Número»;
«Enviado» = solicitada, «Publicado» = concedida) y **traducciones**. No cuentan como artículos,
pero la memoria las informa aparte.

**Filiación:** junto a cada autor del instituto se indica si **firmó la publicación con la
filiación del instituto** (IIMAT, CMAT, FCPN o UMSA; vale la doble filiación). En los informes
institucionales solo cuenta un producto si al menos un autor vinculado al instituto en esa fecha
firmó con ella. Al importar por DOI, se marca sola cuando la afiliación publicada menciona al
instituto o a la UMSA; revísela. En la lista de productos, **«Sin filiación declarada»** muestra
sus artículos indexados o arbitrados pendientes, con botones Sí / No y «Firmé todos estos con
IIMAT/UMSA». Las marcas junto a los autores: ✓ firmó, ✗ no, ? sin declarar.

- **La forma más rápida:** «Nuevo producto» → pegue el **DOI** o el identificador **arXiv** (o su
  dirección) en «Importar» y presione Enter. El formulario se completa con título, autores,
  revista, año, mes y páginas; revíselo y guarde.
  - Si importa un preprint que ya tiene versión publicada, aparece el botón «Importar versión
    publicada»: queda como artículo y conserva el arXiv.
- **Desde BibTeX:** «Importar BibTeX» → suba su archivo `.bib` (el de LaTeX, o el que exportan
  Google Scholar, MathSciNet o Zotero) o pegue las entradas. Verá cada entrada como *nueva*, *ya
  registrada* o *con error* antes de confirmar.
- **A mano:** complete el formulario.

### Autores

- Agregue autores buscando por nombre: primero aparecen los del instituto. Si alguien no existe,
  «Registrar como persona externa» lo crea en el momento.
- Ordénelos con las flechas, en el orden de la publicación.
- Un artículo con varios autores del instituto se registra **una vez** y aparece en el perfil de
  cada uno. Si al escribir el DOI el portal avisa que el producto ya existe, use **«Sumarme como
  autor»** en vez de registrarlo de nuevo.

### Nivel de revisión y el informe del instituto

- Indique si el producto es **indexado** (y en qué índices), **arbitrado** o **sin arbitraje**.
  Los reportes, preprints y presentaciones son siempre sin arbitraje.
- Un producto **cuenta para el informe del instituto** si es indexado o arbitrado y ya está
  aceptado o publicado. Se marca con la etiqueta verde «Cuenta para el informe».
- Lo importado desde DOI o BibTeX queda como *arbitrado*: si la revista está indexada, edítelo
  y marque los índices.

### Adjuntos, edición y exportación

- En la ficha de cada producto puede adjuntar PDF, PNG o JPG (hasta 20 MB). Los adjuntos solo
  los ven quienes pueden editar el registro y la administración.
- Pueden editar el producto quien lo registró y sus autores del instituto; solo quien lo
  registró puede eliminarlo.
- «Exportar BibTeX» descarga lo que está viendo, con los filtros aplicados.

## Actividades

Además de seminarios, congresos y escuelas, registre **estancias o pasantías de investigación**,
**transferencia de conocimiento** (a la sociedad, el sector productivo o las políticas públicas) y su
**participación en redes de investigación** (desde / hasta): IAC-CINDA las considera evidencia de I+D+i.

«Actividades» reúne seminarios, congresos, escuelas, visitas y otras actividades. Al registrar
una, indique el tipo, las fechas, el lugar, la modalidad y el ámbito, y los participantes (del
instituto o externos) con su rol: expositor(a), organizador(a), asistente o comité. En la ficha
puede adjuntar certificados o afiches.

Para una **charla** en un congreso, registre el congreso como actividad y la charla como producto
de tipo «Presentación», vinculada a esa actividad.

## Proyectos

Hay dos tipos de proyecto:

- **Individual:** lo registra usted mismo con **«Nuevo proyecto individual»** y queda como
  responsable. No necesita aprobación. Sirve, por ejemplo, para un proyecto con financiamiento
  externo o una línea de trabajo propia.
- **Institucional:** se propone en la convocatoria de septiembre y lo acepta la administración.
  Rige de octubre a septiembre.

### Proyectos institucionales

- **Quién propone:** investigadores titulares y contratados. Quien propone un proyecto nuevo
  queda como su responsable.
- **Cuándo:** la convocatoria de cada periodo está abierta todo septiembre (la administración
  puede ampliar el plazo). El borrador se puede preparar en cualquier momento; solo el envío
  debe hacerse dentro del plazo. «Proyectos» muestra la convocatoria abierta o la próxima.
- **Cómo:** «Proponer proyecto institucional» crea un borrador. Complete sus secciones: datos
  básicos y objetivos específicos, metodología, resultados esperados, actividades programadas
  (con el mes previsto de cada una) y bibliografía. «Guardar borrador» guarda sin enviar; abajo
  se indica qué falta. Agregue al equipo desde «Gestionar participantes».
- **Después de enviar** no se puede modificar. La administración puede:
  - *aceptarla*: el proyecto rige de octubre a septiembre;
  - *aceptarla con condiciones*: el proyecto queda en espera; corrija la propuesta según las
    condiciones y reenvíela (el reenvío no depende del plazo);
  - *rechazarla*, con el motivo.
  Recibirá la decisión por correo. Mientras no se decide, puede retirarla.
- **Continuidad:** en septiembre, el responsable de un proyecto que termina ve un aviso y el botón
  **«Proponer continuidad»** en el resumen del proyecto (y recibe un correo). La propuesta viene
  precargada con la anterior: actualice los objetivos y ubique las actividades en el nuevo
  calendario. **Si no la presenta, el proyecto concluye el 30 de septiembre.** Si la envió y
  aún no se decide, el proyecto sigue vigente («En renovación») hasta la decisión.
- **Equipo:** el responsable debe ser titular o contratado(a); los co-responsables, además,
  pueden ser interinos.
- En un proyecto institucional, el nombre, la descripción y los objetivos vienen de la propuesta
  aceptada: se cambian en la propuesta de continuidad. Los datos administrativos (código,
  financiamiento, monto) se editan en el resumen.

### Si participa en un proyecto

- En el formulario de un producto o una actividad, marque el proyecto en **«Vincular a
  proyectos»**. Queda **pendiente** hasta que un responsable lo apruebe.
- Si lo rechazan, verá el motivo en «Proyectos → Mis propuestas en revisión» (y por correo, si
  tiene los avisos activos). Corrija el registro y guárdelo con la casilla marcada: se vuelve a
  proponer.
- Mientras está pendiente puede retirarlo desmarcando la casilla.
- En la ficha del proyecto, «Registrar producto del proyecto» abre el formulario con el proyecto
  ya marcado.

### Si es responsable o co-responsable

- El número junto a «Proyectos» en la barra indica cuántas propuestas debe revisar.
- En la pestaña **Pendientes** del proyecto, apruebe o rechace cada propuesta. Al rechazar,
  indique el motivo. Al aprobar una actividad puede asignar su responsable. Un aviso señala
  lo que cae fuera del periodo del proyecto.
- Lo que usted mismo vincula queda aprobado de inmediato.
- En **Participantes** agregue personas del instituto o externas, cambie roles o dé de baja
  (lo ya aprobado se conserva). Puede nombrar co-responsables; cambiar al responsable lo hace
  la administración.
- **Agradecimiento:** los fondos exigen que cada publicación lleve la filiación del instituto y
  **agradezca al proyecto**. Al aprobar un producto indique si lo agradece; en la pestaña
  **Productos** cada uno muestra ambos requisitos y puede corregir el agradecimiento. Quien registra
  el producto también puede indicarlo junto a cada proyecto en el formulario.
- En **Resumen** edite los datos y los objetivos; ahí aparecen también los registros editados
  después de aprobados, por si quiere revisarlos.
- El botón **«Informe»** genera el informe de avance del proyecto.

## Informes

Menú «Informes»:

- **Mi CV:** elija el periodo y, si quiere, «solo lo que cuenta para el informe» o «solo con
  filiación IIMAT/UMSA». Agrupa sus
  productos por categoría y lista actividades y proyectos. Descárguelo con «Imprimir / Guardar
  PDF» (use «Guardar como PDF» en el diálogo del navegador) o en BibTeX.
- **Informe de proyecto:** equipo, objetivos, productos y actividades aprobados en el periodo;
  en los institucionales, además, el plan de actividades (previstas y realizadas). Indica cuántos
  productos cumplen los requisitos de los fondos (filiación y agradecimiento) y qué le falta a cada
  uno. Descarga en XLSX.
- **Memoria del instituto** (administración): ver abajo.

### Plan de actividades (proyectos institucionales)

La pestaña **Plan** del proyecto muestra, por periodo aceptado, las actividades previstas en la
propuesta: *pendiente*, *atrasada* (pasó el mes previsto) o *realizada*. Para marcar una como
realizada, el responsable elige la actividad registrada que la cumple (debe estar aprobada en el
proyecto y ser del mismo periodo).

## Administración

- **Usuarios → Nuevo usuario:** con «Enviar invitación por correo» la persona define su
  contraseña. Sin invitación, el portal muestra una contraseña temporal para entregar a mano.
  Las cuentas de investigador llevan **categoría** (titular, contratado, interino, invitado o
  externo): de ella depende quién puede proponer proyectos institucionales y ser responsable.
- **Usuarios → Importar CSV:** alta masiva desde una planilla con `email`, `nombres`,
  `apellidos` y, opcionalmente, `categoria`, `investigador` y `admin` (sí/no). Las filas sin
  categoría se crean igual y quedan como «Sin categoría». Hay una plantilla. La vista
  previa marca cada fila como nueva, ya existente o con error antes de crear nada.
- En la tabla de usuarios:
  - 🔓 **Desbloquear**: una cuenta bloqueada por intentos fallidos, sin cambiar su contraseña.
  - 🔑 **Restablecer**: genera una contraseña temporal nueva.
  - Activar o desactivar una cuenta; desactivarla cierra su sesión de inmediato.
  - **Vínculo**: el historial de pertenencia al instituto de cada investigador(a), con su
    categoría y jornada por periodo. Desde ahí se registra un cambio de categoría (cierra el
    periodo vigente el día anterior), se termina el vínculo o se agrega un periodo histórico. Los
    informes institucionales solo cuentan lo producido **mientras la persona estaba vinculada**, con
    la categoría de ese momento. Las cuentas sin fecha de ingreso se marcan en ámbar.
  - **Importar historial:** carga el historial desde un CSV de Recursos Humanos (`email`,
    `categoria`, `desde`, `hasta`, `jornada`, `nota`; una fila por periodo). El historial de cada
    persona del archivo se reemplaza por el del archivo.
  - Al **desactivar** una cuenta con vínculo vigente, el portal pregunta si también termina el
    vínculo y en qué fecha. Lo publicado mientras estuvo vinculada sigue contando.
- **Propuestas:** la bandeja de propuestas institucionales por periodo, con filtro por estado y el
  contador de las que esperan decisión. En cada propuesta: aceptar, aceptar con condiciones
  (indicándolas) o rechazar (con el motivo). En la misma página se ajusta el **plazo** de la
  convocatoria (por omisión, todo septiembre) o se abre uno extraordinario.
- **Proyectos:** la administración ve todos los proyectos (con filtro por tipo), pero no los
  gestiona: los datos, participantes y propuestas son de sus responsables. En la ficha de un
  proyecto, **«Reasignar responsable»** cambia al responsable (p. ej., si deja el instituto); el
  anterior sigue como co-investigador(a) o se le da de baja.
- **Informes → Memoria del instituto:** por **año calendario**, **periodo octubre–septiembre** o
  **rango de fechas**. Productos que cuentan (una vez cada uno), actividades, proyectos vigentes
  (institucionales e individuales), un resumen por categoría y otro por investigador; descarga en
  XLSX y CSV. La producción de investigadores externos figura solo si está aprobada en un
  proyecto institucional. En un periodo que no coincide con el año calendario, los productos sin
  mes de publicación cuyo año cae solo en parte dentro del periodo aparecen **«por confirmar»**
  y no se cuentan hasta completar el mes. La sección **«Revistas de los artículos»** separa revistas
  nacionales e internacionales, cuenta las de acceso abierto, los cuartiles y cuántos artículos se
  clasificaron por el catálogo o por lo declarado; **«Datos y método»** explica cómo se calcularon las
  cifras. El XLSX incluye, por producto, la revista, su ámbito, el origen de la clasificación y la
  fuente de cada indexación.
- **Informes → Anexo de I+D+i para la acreditación:** la evidencia de los últimos 5 años (o de los
  años que elija) ordenada según los criterios de IAC-CINDA: resumen por año; cuerpo académico por
  categoría y jornada completa equivalente (2.2.1); publicaciones, libros, patentes, software y
  traducciones (3.6.3 a–e); transferencia, estancias, proyectos, presentaciones y redes (3.6.3 f–j);
  internacionalización (3.5.2) e impacto (3.6.1); lo que el portal aún no registra; y el método. Por
  omisión solo cuenta artículos en revistas verificadas del catálogo; puede incluir las demás. El XLSX
  trae una hoja por criterio.
- **Citas:** en la memoria, «Actualizar citas» consulta en OpenAlex las citas de todos los productos
  con DOI. La sección «Impacto» las suma y el XLSX las trae por producto, con su fecha.
- **Propuestas → Descargar XLSX:** las propuestas presentadas en una convocatoria, con lo que se
  envió (resumen, textos completos, objetivos y actividades previstas), para el comité.
- **Auditoría** (menú con su nombre): quién hizo qué y cuándo, con filtros.
- **Artículos sin revista:** desde el catálogo, los artículos registrados sin revista del catálogo,
  agrupados por el nombre declarado, para vincularlos a una revista o crearla.
- **Catálogo de revistas** (menú con su nombre): las revistas donde publica el instituto y los
  índices en que figuran **cada año**, con la fuente consultada y un enlace de evidencia (lo pide
  IAC-CINDA: datos y métodos transparentes). Una revista **verificada** define el nivel de revisión
  y los índices de los artículos publicados en ella; una **pendiente** todavía no. Se cargan una a
  una o por CSV (una fila por revista e índice; las existentes se completan).

## Preguntas frecuentes

**Registré un artículo y mi coautor(a) del instituto también: ¿quedó duplicado?**
El portal avisa al escribir el DOI o el arXiv. Si igual ocurrió, quien lo registró segundo puede
eliminar el suyo y usar «Sumarme como autor» en el existente.

**¿Por qué mi artículo no aparece en la memoria anual?**
Revise que sea indexado o arbitrado, que esté aceptado o publicado, que el año sea correcto y
que usted figure como autor(a) del instituto.

**¿Quién ve lo que registro?**
Sus colegas ven su perfil y su producción en el directorio interno. Los adjuntos solo los ven
quienes pueden editar el registro. Fuera del instituto solo se ve lo que usted publique con
«Perfil público».

**¿Cómo obtengo el CV en PDF?**
Con «Imprimir / Guardar PDF» (o el menú Imprimir del navegador), elija «Guardar como PDF» como
destino. Al imprimir, el portal oculta la navegación y los botones y usa texto negro sobre blanco
en tamaño A4, aunque en pantalla use el tema oscuro.
