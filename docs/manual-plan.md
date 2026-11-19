# Plan: actualización del manual de usuario (propuesta, 17-nov-2026)

Propuesta de trabajo, **sin decidir**: no está en `PLAN.md`. El manual existente es del 15-nov-2026 y describe el sistema
como era cuando solo servía a la Carrera de Matemática. Desde entonces el sistema se volvió modular (PLAN §73) y
independiente de una unidad (PLAN §74).

## 1. Situación

- **El manual actual** son 15 capítulos en HTML (unas 17.000 palabras), 116 capturas y un PDF de 30 MB. Describe un
  sistema con todos los módulos activos y la marca de la Carrera de Matemática.
- **Decisión del 17-nov-2026:** el manual de Matemática **sale del repositorio público**. Vive en
  `instancias/cmat/manual/`, junto al resto de lo propio de esa Carrera, y `scripts/manual.py` lo arma desde ahí con la
  marca de la instancia (`--manual CARPETA` o `TAU_MANUAL` para otra carpeta). Sin esa carpeta, quien clone el
  repositorio no tiene manual.
- **Actualizado el 18-nov-2026 (manual de Matemática):** se reescribieron los capítulos 1 a 4, 9, 11 y 12, se ajustaron 0, 5 a 8, 10 y 13,
  se agregaron «Módulos y perfiles» (14) e «Instalarlo en el teléfono» (15) y se retomaron las capturas (120) con datos ficticios nuevos
  de calidad. Lo de abajo describe lo que faltaba y sigue siendo la base del manual **genérico**, que no existe aún.
- **Lo que estaba desactualizado** (15-nov-2026 en adelante): el menú de las capturas, los pendientes y el calendario (hoy
  son una sola pantalla), las migas de pan, la administración de módulos y de unidades, los perfiles de instalación, el
  «Primeros pasos» del primer día, las cifras de calidad «sin fuente», la página de privacidad que cambia con los
  módulos activos y la instalación en el teléfono.

## 2. Qué manual se quiere

Hoy hay un solo manual y es de Matemática. Con un sistema que instalan varias unidades hacen falta dos cosas distintas:

| | Manual del sistema | Manual de una instancia |
|---|---|---|
| Quién lo lee | Cualquier usuario de TAU en cualquier unidad | Usuarios de una unidad concreta |
| Qué cuenta | Cómo funciona cada módulo, los roles, los procesos | Lo propio: reglamentos, nombres de cargos, plazos, a quién acudir |
| Capturas | Instancia de ejemplo (genérica), marca genérica | Su propia marca y sus datos |
| Dónde vive | En el repositorio, generado con `instancias/ejemplo` | En su instancia (`instancias/<nombre>/manual/`) |

**Propuesta:** escribir el manual del sistema (genérico) y que el de cada unidad sea una **capa encima**: sus capítulos
propios más los del sistema. El de Matemática ya existe y pasaría a ser esa capa, con los capítulos genéricos
reemplazados por los nuevos.

## 3. Qué hay que cambiar en el contenido

| Capítulo | Cambio |
|---|---|
| 00 Sobre este manual | Dice a quién va dirigido; ya no es «el manual de la Carrera de Matemática» |
| 01 Qué es TAU | Un sistema modular que cada unidad ajusta; qué es una instancia; qué módulos hay |
| 02 Cómo está organizado | Menú nuevo (grupos por módulo, «Mis pendientes» y «Mi calendario» bajo «Inicio», migas de pan); qué cambia cuando un módulo está apagado |
| 03 Usuarios, roles y privilegios | Roles por tipo de unidad; quién activa módulos (Administración del sistema) |
| 04 Primeros pasos | **Reescribir:** el primer día de una instalación nueva («Primeros pasos», módulos, unidades, primeras cuentas) |
| 05 a 09 Investigación, Docencia, Estudiantes, Servicios, Calidad | Capturas nuevas; una nota por capítulo de «este módulo puede estar apagado»; en Calidad, los indicadores «sin fuente»; en Docencia, el historial por módulos |
| 10 Informes | Membrete con la marca de la unidad y logo del instituto opcional |
| 11 Administración | **Reescribir:** Módulos (con requisitos y aviso de lo que queda en curso), Unidades, auditoría |
| 12 Privacidad y IA | La página de privacidad muestra solo lo que trata cada módulo activo; con la IA apagada no hay botones |
| 13 Preguntas y glosario | Términos nuevos: módulo, perfil, instancia, «sin fuente» |
| **Nuevo:** Instalarlo en el teléfono | Una página: qué es y cómo se instala |
| **Nuevo:** Módulos y perfiles | Para quien administra: qué hace cada módulo, qué necesita y qué perfil elegir |

Estimación: el 30 % de las 17.000 palabras cambia o se agrega; el resto se conserva.

## 4. Qué hay que resolver antes

1. **Datos de demostración para la instancia de ejemplo.** Hoy las capturas salen de `scripts/seed.py`, que es de
   Matemática (docentes, MAT-111, proyectos del instituto). Un manual genérico necesita docentes, productos, proyectos,
   estudiantes, una oferta y una autoevaluación ficticios y neutros, que cargue un `seed` de la instancia de ejemplo.
   **Es el trabajo más grande y no está hecho.**
2. **`scripts/manual.py` sin supuestos de Matemática.** Hecho el 17-nov-2026 lo que dependía del lugar (dónde vive el
   manual, rutas a `static/`, siglas fijas). Queda `datos()`: nombra «Licenciatura en Matemática», `MAT-111`, la
   Olimpiada Boliviana de Matemática y similares. Debería tomar sus nombres de la instancia.
3. **Dónde se publica.** Un PDF de 30 MB no se lleva bien en git. Conviene no versionarlo: publicarlo como archivo
   adjunto de una versión (Releases) o generarlo al desplegar.

## 5. Etapas

Cada una es un commit. Esfuerzos gruesos, **sin medir**.

| Etapa | Qué se hace | Esfuerzo |
|---|---|---|
| **M0. Dependencias del script** | `manual.py` vive en la instancia; rutas, siglas y mensajes | Hecha (17-nov-2026) |
| **M1. Datos de demostración genéricos** | Seed de la instancia de ejemplo y `datos()` sin nombres de Matemática | 2–3 días |
| **M2. Capítulos nuevos y reescritos** | 04, 11, los dos capítulos nuevos y las notas de módulo apagado | 2–3 días |
| **M3. Capítulos con cambios menores** | 00 a 03, 05 a 10, 12 y 13; la lista de capturas en `CAPTURAS` | 2 días |
| **M4. Capturas y PDF** | Tomar las ~120 capturas, armar el PDF, revisar página por página | 1 día |
| **M5. Manual de Matemática como capa** | Reponer sus capítulos propios sobre los del sistema | 1 día |

## 6. Decisiones que hacen falta

1. **¿El manual genérico entra al repositorio público?** Propuesta: los capítulos y el script, sí; el PDF y las
   capturas, no (se generan o se adjuntan a una versión).
2. **¿Una sola capa o varias?** Si una tercera unidad pide su manual, ¿se copia la carpeta del de Matemática o se
   arma con el del sistema más sus capítulos? Propuesta: lo segundo.
3. **¿Quién mantiene los datos de demostración?** Cada instancia que quiera manual necesita los suyos.
