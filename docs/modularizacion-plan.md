# Plan de modularización de TAU (propuesta, 15-nov-2026)

Propuesta de trabajo, **no es una decisión del instituto** ni está en `PLAN.md`. Sigue a
[liberacion-borrador.md](liberacion-borrador.md) y lo corrige en tres puntos (§2). Objetivo: que la misma base de
código sirva a cualquier unidad de la UMSA, con lo mínimo activo por defecto y el resto habilitable desde un panel de
Administración del sistema.

## 1. Lo que muestra el código hoy

Medido sobre `app/` (análisis de imports archivo por archivo, registro de rutas, menú y permisos):

- **La estructura ya ayuda.** Cada archivo de `app/<paquete>/rutas/` es un `APIRouter()` propio (unos 105 archivos, unas
  830 rutas) y cada paquete los entrega con `routers()`. Un archivo de rutas pertenece a una sola función del sistema:
  la unidad natural de corte ya existe.
- **`comun` no importa de nadie.** Es una plataforma real.
- **El paquete de Python no coincide con el módulo funcional.** Tres casos:
  - `app/calidad` mezcla dos cosas: los **informes de investigación** (memoria, I+D+i, CV, listados, informes
    programados; unos 2.500 renglones en `informes.py`, `anexo.py`, `listados.py`, `programados.py` y sus rutas) y el
    **SIAC** (marco, indicadores, evidencias, autoevaluación, plan de mejora). Por eso `investigacion/rutas/bibtex.py`
    importa de `calidad`.
  - `app/investigacion/adjuntos.py` (85 renglones) es infraestructura: lo usan `calidad`, `estudiantil` y cinco
    archivos de `servicios`.
  - `app/estudiantil/rutas/estudiante.py` hace de base del portal del estudiante: lo importan siete archivos de
    `servicios`.
- **Los nudos son agregadores, no lógica.** Casi todos los cruces entre paquetes están en pantallas o procesos que
  juntan cosas de varios módulos:

  | Agregador | Hoy importa de |
  |---|---|
  | `app/navegacion.py` (menú) | academico, calidad, servicios, y consulta tablas de auxiliaturas y grado |
  | `app/inicio.py` (página de inicio) | academico, calidad, estudiantil, investigacion (15 módulos) |
  | `app/busqueda.py` | investigacion |
  | `mis_pendientes` (investigación y docencia) | academico, calidad, estudiantil |
  | `estudiantil/calendario.py` | academico, servicios |
  | `academico/docente.py` e `historial.py` | servicios (auxiliaturas, grado), estudiantil, calidad |
  | `main._correr_mantenimiento` | investigacion, calidad, egresados, servicios |
  | `ia/catalogo.py` | investigacion, calidad |
  | `privacidad.FORMULARIOS`, `paquete.ARCHIVOS` | listas fijas con rutas y tablas de varios módulos |
  | `calidad/indicadores.py`, `ficha.py`, `seguimiento_estudiantil.py` | estudiantil, egresados, academico |

- **La organización está incrustada.** `permisos.ROLES` asigna cada rol a siglas fijas (`UMSA`, `IIMAT`, `CMAT`),
  `unidades.py` tiene `INSTITUTO = "IIMAT"` y `CARRERA = "CMAT"`, y la migración `0022` siembra las cuatro unidades. El
  modelo supone una carrera **con** su instituto. Para otra unidad esto pesa más que cualquier módulo.
- **No existe una tabla de ajustes del sistema**: toda la configuración es de entorno (`app/comun/config.py`).

## 2. Qué cambia respecto del borrador

1. **Módulo funcional ≠ paquete de Python.** No se reorganizan carpetas para modularizar: un módulo se declara en un
   manifiesto que lista sus archivos de rutas. Mover código queda para los tres casos del §1, y solo cuando haga falta.
2. **El núcleo es más chico de lo propuesto.** Investigación no es «estrictamente necesaria»: una carrera sin instituto
   no la usa, y un instituto no usa docencia. Lo único común a toda unidad es la plataforma (personas, vínculos,
   unidades, roles, avisos, auditoría). Investigación y docencia pasan a ser módulos, y la instalación elige un
   **perfil** (§5).
3. **Auxiliaturas se queda en la versión libre.** El borrador la sacaba por llevar el reglamento en el código, pero ese
   reglamento es una resolución del HCU (424/2023), es decir, de toda la UMSA: es justamente lo que otras carreras
   pueden reusar. Va como módulo opcional. Lo que sí sale a la instancia son los **datos** de la Carrera (planes en CSV,
   marco de calidad, plan de mejora, marca).

Respuesta a «¿los especializados o todos?»: **todos los módulos funcionales se pueden apagar; la plataforma no.** Hacer
conmutable solo a los «especializados» obligaría a decidir hoy qué necesita una unidad que todavía no conocemos.

## 3. Arquitectura propuesta

### 3.1 Tres capas

| Capa | Contenido | Se apaga |
|---|---|---|
| **Plataforma** | Cuentas e ingreso, roles y permisos, unidades, vínculos y categoría, personas externas, avisos, correo, auditoría, privacidad, adjuntos, búsqueda, inicio, menú, mis datos, panel de módulos | No |
| **Módulos** | Las 17 funciones del §4, cada una con su manifiesto | Sí, desde el panel |
| **Instancia** | Datos y marca de una unidad: unidades y siglas, planes de estudio, marco de calidad, logotipos, textos de privacidad | No es código |

### 3.2 El manifiesto de un módulo

`app/comun/modulos.py` define el registro (clase, estado, `activo(clave)`), sin importar de otros paquetes. Cada paquete
declara sus módulos en `app/<paquete>/modulo.py`. Un manifiesto dice, de forma declarativa:

- `clave`, `nombre`, `descripcion` (una frase para el panel), `area` y `requiere` (otros módulos);
- `rutas`: los archivos de rutas que le pertenecen;
- `acciones`: las acciones de `permisos.ACCIONES` que son suyas;
- lo que aporta a cada **punto de extensión** (§3.4).

Sin descubrimiento dinámico ni paquetes instalables: `main.py` carga una lista fija de manifiestos. Es el patrón más
simple que resuelve el problema y no agrega dependencias.

### 3.3 El cierre: una sola compuerta, tres defensas

1. **Compuerta de rutas.** Todos los routers se montan siempre (así el panel surte efecto sin reiniciar). Al
   registrarlos, `main.py` arma el mapa ruta → módulo desde `router.routes`. Un `Beforeware` sin excepciones, el
   primero de la cadena, responde 404 si el módulo de la ruta está apagado. Cubre también `/publico/*`, `/api/v1/*`,
   `/encuesta/<enlace>` y los parciales HTMX, que hoy saltan `_cargar_usuario` por `RUTAS_PUBLICAS`. Starlette deja la
   ruta resuelta en `scope["route"]`; hay que confirmar con una prueba corta que el `Beforeware` de FastHTML la ve.
2. **Permisos.** `permisos.puede()` devuelve falso para una acción de un módulo apagado. Con eso desaparecen solos los
   botones y enlaces que otros módulos muestran condicionados a un permiso.
3. **Menú.** Cada módulo aporta sus ítems; `navegacion.menu` solo los ordena en grupos.

El estado vive en una tabla `modulo` (clave, activo, quién y cuándo), con caché en memoria que se invalida al cambiar.
Cada cambio queda en la auditoría.

### 3.4 Puntos de extensión (lo que deshace los nudos)

Los agregadores dejan de importar módulos: recorren lo que los módulos **activos** registraron.

| Punto | Reemplaza |
|---|---|
| `menu` | la función única de `navegacion.py` (grupos del personal y del estudiante) |
| `inicio` | los bloques de `app/inicio.py` |
| `busqueda` | `busqueda.GRUPOS` |
| `pendientes` | los dos `mis_pendientes` |
| `calendario` | `estudiantil/calendario.py` y los calendarios del docente y del investigador |
| `mantenimiento` | la lista de `main._correr_mantenimiento` |
| `historial_docente` | los cruces de `academico/docente.py` e `historial.py` con auxiliaturas y grado |
| `fuentes_de_indicadores` | los cálculos de `calidad/indicadores.py` sobre estudiantes, egresados y docencia |
| `funciones_ia` | `ia/catalogo.py` |
| `privacidad` y `archivos` | `privacidad.FORMULARIOS` y `paquete.ARCHIVOS` |

### 3.5 Reglas de dependencia, vigiladas por una prueba

- Un módulo importa de la plataforma y de los módulos que declara en `requiere`. Nada más.
- Lo opcional entre módulos pasa por un punto de extensión.
- `tests/test_arquitectura.py` recorre los imports (el mismo análisis de este plan) y falla ante un cruce no
  declarado. Arranca con la matriz actual como **línea base que solo puede achicarse**: no exige arreglar todo de una
  vez, pero impide empeorar.

### 3.6 Datos y esquema

- Las 95 migraciones no se tocan y las 171 tablas existen siempre. **Apagar oculta; nunca borra.** Reactivar devuelve
  todo como estaba. Por eso las consultas SQL que cruzan módulos no son un obstáculo.
- Un módulo apagado no corre tareas de fondo, no envía correos ni avisos y no aparece en el respaldo como faltante.
- Antes de apagar, el panel avisa lo que queda en curso (por ejemplo, una convocatoria publicada o una encuesta
  abierta). Cada módulo declara esa comprobación.

### 3.7 Tres estados, para la «versión reducida»

Un módulo está **activo**, **apagado** (código presente) o **ausente** (su carpeta no está en la distribución). El
registro tolera manifiestos ausentes. Cuando la prueba de arquitectura muestre que nadie importa un módulo desde
fuera, ese módulo puede quitarse del árbol sin que el sistema deje de arrancar. Así la versión reducida es la misma
base de código con menos carpetas, no una bifurcación.

## 4. Catálogo de módulos

| Área | Módulo | Contenido | Requiere | Hoy en |
|---|---|---|---|---|
| Investigación | `investigacion` | Perfiles, productos, actividades, proyectos y propuestas, importaciones, catálogos, perfil público y API, acceso abierto, colaboraciones | — | `investigacion` |
| Investigación | `informes` | Memoria, I+D+i, CV, listados, informes programados, calidad de datos | `investigacion` | `calidad` |
| Docencia | `planes` | Reformas, planes, malla, menciones, equivalencias, vigencia | — | `academico` |
| Docencia | `oferta` | Gestiones, oferta, asignación docente, carga asignada, mi docencia, preferencias, programas, listas de curso | `planes` | `academico` |
| Docencia | `evaluacion_docente` | Evaluación docente anónima | `oferta`, `estudiantes` | `academico`, `estudiantil` |
| Estudiantes | `estudiantes` | Cohortes, carga del CSV, rendimiento, actividad estudiantil y portal del estudiante | — | `estudiantil`, `comun` |
| Estudiantes | `encuestas` | Encuestas y su retorno | `estudiantes` | `estudiantil` |
| Estudiantes | `tutoria_apoyo` | Tutoría, apoyo estudiantil, orientación y buzón | `estudiantes` | `estudiantil` |
| Estudiantes | `egresados` | Titulación, seguimiento, directorio y empleadores | `estudiantes`, `encuestas` | `egresados` |
| Servicios | `comunicados` | Comunicados y eventos con convocados | — | `servicios` |
| Servicios | `auxiliaturas` | Convocatorias, comisión, calificación, designaciones y formularios | `oferta`, `estudiantes` | `servicios` |
| Servicios | `grado` | Proyectos de grado, tribunales y temas de grado | `estudiantes` | `servicios` |
| Servicios | `oportunidades` | Oportunidades, biblioteca y recursos | `estudiantes` | `servicios` |
| Calidad | `calidad` | Marco, indicadores, evidencias, autoevaluación, ficha, capacitación, convenios, impacto, indicadores públicos | — | `calidad` |
| Calidad | `mejora` | Plan de mejora, actividades, cortes y reprogramaciones | `calidad` | `calidad` |
| Transversal | `ia` | IA con criterio humano | — | `ia` |
| Transversal | `piloto` | Comentarios y tablero del piloto | — | `comun` |

Notas:

- Algunos informes de `informes` usan docencia (carga docente, cuerpo académico): aparecen solo si `oferta` está
  activo. Lo mismo vale para «Mi plan de estudios» del estudiante respecto de `planes`.
- `calidad` no exige otros módulos: un indicador cuya fuente está apagada queda como cifra manual.
- No se parte `investigacion` en producción y proyectos: están muy unidos y ninguna unidad pediría una sin la otra.
  Criterio general: un módulo existe solo si alguna unidad querría apagarlo dejando encendido a su vecino.

## 5. Perfiles de instalación y el panel

Al instalar se elige un perfil, que es solo un conjunto inicial de módulos. Después manda el panel.

| Perfil | Módulos activos |
|---|---|
| **Mínimo** (por defecto) | Solo la plataforma y `comunicados` |
| **Instituto** | `investigacion`, `informes`, `comunicados` |
| **Carrera** | `planes`, `oferta`, `estudiantes`, `comunicados` |
| **Carrera con instituto** | Los dos anteriores |
| **Completo** | Todos (la instancia actual de la Carrera de Matemática) |

- El perfil sale de una variable de entorno (`TAU_PERFIL`) solo cuando la base es nueva. La base actual migra con
  **todos activos**: el piloto no nota ningún cambio.
- Panel en Administración → Módulos, solo para Administración del sistema: módulos agrupados por área, una frase de
  cada uno, sus requisitos, y el aviso de lo que queda en curso al apagar. Activar uno activa sus requisitos, previa
  confirmación; no deja apagar uno del que depende otro activo.
- Para quien administra son 17 interruptores en 6 grupos. No hay nada más que aprender.

## 6. Etapas

**Estado (16-nov-2026):** etapas 0 a 6 hechas (ver §10). El detalle de lo construido y de las asignaciones de cada archivo de
rutas a su módulo está en `PLAN.md` §73; el catálogo real, en `app/<paquete>/modulo.py`. Diferencias con este plan: los
perfiles y `TAU_PERFIL` se adelantaron a la etapa 1 (hacían falta para decidir el estado de una base nueva), el menú
ya oculta lo apagado y las tareas periódicas ya respetan el módulo; el informe del cuerpo académico quedó en `oferta` y
el de seguimiento estudiantil en `estudiantes`.

Cada etapa es un commit con sus pruebas. Los esfuerzos son estimaciones gruesas, sin medir.

| Etapa | Qué se hace | Efecto para el piloto | Esfuerzo |
|---|---|---|---|
| **0. Línea base** | Prueba de arquitectura con la matriz actual; decisiones del §8 en `PLAN.md` | Ninguno | 1–2 días |
| **1. Registro y compuerta** | `comun/modulos.py`, manifiestos (rutas y acciones), tabla `modulo`, compuerta 404, `puede()` por módulo, panel. Todo activo | Ninguno; aparece una pantalla de administración | 4–6 días |
| **2. Menú, inicio y búsqueda** | Los tres pasan a puntos de extensión | Mismas pantallas, armadas de otro modo | 4–6 días |
| **3. Procesos y listas** | Mantenimiento, pendientes, calendario, privacidad, respaldo | Ninguno visible | 4–6 días |
| **4. Nudos de código** | `adjuntos` a `comun`; base del portal del estudiante; informes fuera de `calidad`; historial docente; fuentes de indicadores; funciones de IA | Ninguno visible; es la de más riesgo | 6–10 días |
| **5. Perfiles** | `TAU_PERFIL`, seed por perfil, CI con el perfil mínimo y con cada módulo apagado | Ninguno | 4–6 días |
| **6. Organización** | Roles por tipo de unidad en vez de siglas; unidades como dato de instancia | Requiere decisiones (§8) | 4–8 días |

Las etapas 0 y 1 no cambian el comportamiento y caben durante el piloto. Las etapas 2 a 4 reescriben pantallas que el
piloto usa todos los días (menú, inicio, pendientes): conviene hacerlas al concluir el piloto o en una ventana acordada.
`PLAN §72` congela módulos nuevos; esto no agrega ninguno, pero la decisión de cuándo tocar esas pantallas es de la
Dirección.

Después de la etapa 6 siguen las tareas del borrador que no son de modularización: marca genérica, literales
institucionales, licencia y expediente.

## 7. Pruebas que sostienen el diseño

- **Toda ruta pertenece a un módulo o a la plataforma** (hermana de `tests/test_rutas_declaradas.py`).
- **Módulo apagado = 404 en todas sus rutas**, recorriendo el registro, también las públicas y la API.
- **Ningún enlace del menú, del inicio ni de la búsqueda lleva a un 404**, con cada módulo apagado por turno.
- **Cierre de dependencias**: no se puede dejar activo un módulo sin sus requisitos.
- **Arquitectura**: la matriz de imports solo se achica.
- **Perfil mínimo**: el sistema arranca, se ingresa y se recorre sin errores con todos los módulos apagados.
- Las ~1.100 pruebas actuales siguen corriendo con todos los módulos activos.

## 8. Decisiones

Tomadas por el usuario el 15-nov-2026 (registradas en `PLAN.md` §73):

1. **Vínculos:** los define siempre la Dirección de Carrera, máxima instancia ejecutiva. Consecuencia para el diseño:
   una instalación de TAU es de una carrera; el instituto es una unidad opcional dentro de ella. El perfil «Instituto»
   es entonces una carrera que solo activa investigación, no una instalación sin carrera (confirmado).
2. **Roles por tipo de unidad** para la liberación, sin siglas fijas en el código (etapa 6).
3. **El piloto sigue en pausa:** las etapas 2 a 4 no esperan.
4. **El perfil por defecto es «Mínimo».**

5. **El módulo `grado` se ofrece a otras carreras.** Es el de proyectos de grado: el trámite de titulación del
   estudiante (perfil y documento final, tutor, tribunal, revisiones, plantilla LaTeX) más los temas de grado que
   publican los docentes; no el grado académico de los docentes, que es de la plataforma. Sus plazos (hoy 15 días
   hábiles) y su plantilla pasan a ser parámetros de la instancia.

## 9. Riesgos

- **La compuerta es seguridad.** Un hueco deja expuesto un módulo que se creía apagado. Por eso va en un solo lugar y
  con una prueba que recorre todas las rutas.
- **Rutas compartidas.** Algunas direcciones cruzan módulos (por ejemplo, `calidad/rutas/informes.py` sirve rutas bajo
  `/proyectos/{pid}`). El mapa se arma por archivo de rutas, no por prefijo de la dirección.
- **Costo de mantenimiento.** Cada combinación de módulos es un sistema distinto. Se prueban el perfil mínimo, el
  completo y cada módulo apagado por separado; no todas las combinaciones.
- **Reglas de privacidad.** Los puntos de extensión no deben abrir datos entre módulos: cada aporte conserva su propio
  control de acceso (tutoría confidencial, lista de curso, evaluación docente, marcas privadas del estudiante).

## 10. Cómo quedó (16-nov-2026)

Las etapas 0 a 6 están hechas. El registro de lo construido, las decisiones, lo medido y las mejoras propuestas están
en `PLAN.md` §73 («Etapas» y «Evaluación final»). Este documento conserva el diseño original; donde difiere de lo
hecho, manda `PLAN.md`:

- Los perfiles se adelantaron a la etapa 1 y el estado «ausente» (§3.7) no se implementó: los nudos que quedan
  impiden quitar carpetas, así que no había un caso real que atender.
- No se unificaron las pantallas de pendientes y calendario: se desacoplaron sus datos (punto `pendientes` y `eventos`).
- El respaldo no se modularizó: lleva siempre todos los archivos, porque apagar no borra.
- `fuentes_de_indicadores`, `historial_docente` y `funciones_ia` (§3.4) no se hicieron: son los nudos que quedan.
- Para agregar un módulo o una pantalla: `CLAUDE.md` («Módulos») y la skill `nueva-ruta-o-permiso`.
- Después de la evaluación se hicieron las ocho mejoras propuestas (informes en `app/informes`, indicadores «sin
  fuente», una pantalla de pendientes y una de calendario, unidades editables, historial docente por aportes, reloj
  propio para las tareas, pruebas más cortas, migas de pan y manifiesto web): `PLAN.md` §73, «Mejoras posteriores».

