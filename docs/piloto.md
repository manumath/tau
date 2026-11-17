# Guía del piloto con usuarios reales (PLAN §72, etapa 9)

El piloto prueba TAU con personas reales de la Carrera antes de abrirlo a todos.

> **En pausa desde el 15-nov-2026:** el piloto se suspendió para hacer nuevas modificaciones al sistema y ya no rige
> el congelamiento de módulos (PLAN §72). Esta guía queda como plan para cuando se retome; antes de empezar, revise que
> las tareas por rol y las fechas sigan valiendo.

## 1. Quiénes y cuándo

Entran todos los roles (decisión del 14-nov-2026), **escalonados** para que el equipo pueda acompañar a cada grupo. Cada
grupo usa el sistema **cuatro semanas** contadas desde que entra.

| Semana de ingreso | Grupo | Personas | Con qué empieza |
|---|---|---|---|
| 1 | Dirección de Carrera, Dirección del Instituto y Comisión de calidad | 3 a 5 | Plan de mejora |
| 2 | Coordinación académica y docentes e investigadores | 3 a 5 por rol | Mis pendientes, perfil y producción |
| 3 | Estudiantes | 3 a 5 | Mi seguimiento y servicios |

Elija personas dispuestas a comentar y que representen usos distintos (por ejemplo, un docente titular y uno contratado;
estudiantes de primeros y de últimos semestres).

## 2. Antes de empezar: datos reales y su responsable

Ningún dato real entra al repositorio: se cargan solo en el servidor del piloto.

| Dato | Cómo se carga | Responsable |
|---|---|---|
| Personas, cuentas y roles | Administración → Usuarios (importar CSV) | Administración del sistema, a pedido de las direcciones |
| Categoría, vínculo y carga horaria | Administración → Usuarios → vínculo | Dirección de Carrera |
| Plan de estudios vigente | Docencia → Planes de estudio | Dirección de Carrera y Coordinación académica |
| Gestión en curso y oferta | Docencia → Gestiones y oferta | Coordinación académica (la activa la Dirección de Carrera) |
| Plan de mejora 2026–2030 | Calidad → Plan de mejora → Cargar CSV (`datos/calidad/plan-de-mejora-2026-2030.csv`) | Dirección de Carrera |
| Cohortes de estudiantes | Estudiantes → Cohortes → Cargar CSV (Seguimiento Académico) | Gestión de datos |
| Vacantes y rendimiento por asignatura | Cohortes → Vacantes / Rendimiento | Dirección de Carrera y Gestión de datos |

Antes de cargar: haga un respaldo y un simulacro de restauración (`scripts/restaurar_prueba.sh`, ver
`docs/mantenimiento.md` §5.3); el de la réplica de Litestream del servidor sigue pendiente. Verifique también dónde
pueden alojarse los datos de los estudiantes (`docs/gobernanza.md` §4). Revise con la Dirección de Carrera los textos de la página **Privacidad**
(`/publico/privacidad`): son el compromiso público del sistema.

## 3. Cómo se recogen las opiniones

- **Comentar esta pantalla.** Con `TAU_PILOTO=1`, cada pantalla lleva al pie el botón **Comentar esta pantalla**. Se
  guarda el texto, la pantalla (sin los números de la dirección) y el rol, nunca el nombre. La Administración del sistema
  los ve en **Administración → Piloto y adopción** y los marca como atendidos, con una nota de lo que se hizo.
- **Adopción.** En la misma pantalla, por rol y por semana: cuántas personas entraron y cuántas registraron algo. Sale
  de la auditoría; no muestra nombres.
- **Encuesta de cierre.** Al terminar las cuatro semanas de cada grupo, una encuesta **anónima** del módulo de encuestas
  (Estudiantes → Encuestas) con las diez preguntas de la escala de usabilidad SUS (escala de 1 a 5) y dos abiertas: «¿Qué fue
  lo más útil?» y «¿Qué cambiaría primero?». Recuerde que los resultados de una encuesta anónima se muestran con 5
  respuestas o más.

## 4. Cinco tareas por rol

Pida a cada persona que haga estas tareas en la primera semana y que comente donde se trabe. Lo esperado es que las
termine sin ayuda.

**Dirección de Carrera**
1. Cargar el plan de mejora desde el CSV y revisar a quién propone el sistema como responsable de cada acción.
2. Registrar la aprobación del plan (resolución y fecha).
3. Resolver una reprogramación pendiente (aprobar o rechazar con motivo).
4. Abrir un corte trimestral, leer lo que pide atención y cerrarlo.
5. Registrar las vacantes de la última admisión y revisar la cobertura.

**Dirección del Instituto**
1. Revisar los proyectos institucionales vigentes y su equipo.
2. Ver el cronograma del plan de mejora y las actividades a cargo del Instituto.
3. Registrar el avance de una actividad del plan a su cargo.
4. Generar la memoria o el informe de I+D+i del año.
5. Revisar el perfil público de un investigador.

**Comisión de calidad**
1. Comentar las actividades que piden atención en un corte abierto.
2. Revisar la ficha estadística y su descarga.
3. Registrar una evidencia de un criterio.
4. Revisar los indicadores del año y su base (n).
5. Ver el plan de mejora por prioridad y por responsable.

**Coordinación académica**
1. Revisar la oferta de la gestión en planificación.
2. Asignar un docente a un paralelo.
3. Revisar la carga horaria de un docente.
4. Preparar una convocatoria a auxiliatura.
5. Revisar el rendimiento por asignatura de la última gestión cargada.

**Docentes e investigadores**
1. Revisar Mis pendientes y el calendario.
2. Registrar el avance de su actividad del plan de mejora desde Mis pendientes, con su evidencia adjunta, si tiene una.
3. Registrar un producto (por DOI o a mano) y revisar el perfil público.
4. Completar las preferencias de oferta.
5. Pedir una reprogramación de una actividad, si corresponde.

**Estudiantes**
1. Ingresar con el enlace al correo y aceptar el uso de datos.
2. Declarar una actividad (ayudantía, olimpiada…) con su evidencia.
3. Revisar Mi plan de estudios y marcar las materias aprobadas.
4. Enviar una consulta al buzón (con nombre o anónima).
5. Responder una encuesta.

## 5. Cierre del piloto

Al terminar el último grupo: lea los comentarios pendientes, la adopción por rol y la encuesta de cierre; anote en PLAN.md
(con fecha) qué se corrigió, qué quedó pendiente y si el sistema se abre a todos. Desactive `TAU_PILOTO`.
