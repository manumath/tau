# Usabilidad por tipo de usuario y aporte del stack

Material de apoyo para el **Informe de Autoevaluación** de la Carrera (al día al 15-nov-2026). Como el resto del
sistema, no nombra a ninguna agencia acreditadora (PLAN §57). Explica cómo el diseño y el *stack* tecnológico de TAU se traducen en usabilidad para cada perfil de
usuario y en evidencia confiable y trazable para el proceso de acreditación.

TAU se organiza en **perfiles con permisos acotados por rol, unidad y vigencia**
(`app/comun/permisos.py`). Cada actor accede solo a lo que su función necesita, y la interfaz se adapta
a ese rol (inicio «Para hoy», menús y acciones visibles). El sistema no exige instalar software ni
aprender una herramienta técnica: se usa desde el navegador con el correo institucional.

## Panorama por perfil

| Perfil | Qué hace en el sistema | Beneficio de usabilidad |
|---|---|---|
| **Investigador(a) / docente** | Registra su perfil, productos y actividades; importa por DOI/arXiv/BibTeX u OpenAlex; genera su CV. | Una sola captura de datos alimenta CV, informes y memoria; formularios asistidos, detección de duplicados, autocompletado de revista y clasificación MSC2020. |
| **Responsable / co-responsable de proyecto** | Gestiona el proyecto, aprueba o rechaza propuestas, asigna carga y filiación. | Bandeja de pendientes con contador, avisos por correo, confirmar/deshacer y trazabilidad de lo aprobado. |
| **Participante de proyecto** | Propone sus actividades y productos; ve el estado de sus propuestas. | Flujo *propuesta → aprobación* comprensible, con motivo de rechazo y reintento en un clic. |
| **Dirección de Carrera** | Define categoría, vínculo y carga horaria; planes, oferta y asignación docente. | Acciones masivas (grilla, copiar semestre, renovar contratos), tablero «Preparación del semestre» y validaciones en servidor que evitan inconsistencias de carga. |
| **Dirección del Instituto** | Ciclo de vida de proyectos institucionales, catálogos, memoria y anexo. | Propuesta con barra de requisitos y etapas fechadas; continuidad precargada; decisiones con registro. |
| **Coordinación académica / Gestión de datos** | Planes, oferta, asignación; fichas académicas y estudiantes. | Misma lógica de rol acotado; avisos «Avisar a N personas» para completar datos pendientes. |
| **Administración del sistema** | Cuentas, roles, auditoría, alta masiva por CSV. | Vista previa antes de crear, asignación de roles con fecha y unidad, auditoría exportable. |
| **Comisión de calidad** | Ve todo; registra evidencias y los juicios de la autoevaluación, y comenta los cortes del plan de mejora. | Indicadores con su base (n) y su fórmula, evidencias con huella, ficha estadística, memoria e informe de I+D+i al alcance, sin poder alterar los datos de origen. |
| **Responsable de una actividad del plan de mejora** | Registra el avance y adjunta su evidencia desde «Mis pendientes»; pide reprogramaciones. | No necesita un rol ni conocer el repositorio de evidencias: el sistema liga el archivo a su actividad. |
| **Estudiante** | Ingresa con un enlace al correo: su seguimiento, plan de estudios, tutoría, encuestas, auxiliaturas, grado y servicios. | Sin contraseña que recordar; ve solo lo suyo, y sus marcas y señales de apoyo son privadas. |
| **Persona externa / tesista** | Figura como coautor o participante (no accede). | Su rastro queda trazado sin abrir cuentas; unifica duplicados y conserva periodos de estudiante para los indicadores. |
| **Público externo** | Perfil público opcional, directorio y API JSON de solo lectura. | Difusión de la producción sin exponer datos sensibles (sin correo, fechas de nacimiento ni adjuntos). |

## Por qué el stack produce esa usabilidad

**1. HTML servido desde el servidor + HTMX (FastHTML).** Las pantallas son páginas ligeras que se
actualizan por fragmentos, sin una aplicación cliente pesada. Resultado: arranque rápido incluso en
equipos modestos y enlaces reales por página (filtros y búsquedas quedan en la URL, se comparten y se
guardan como favoritos). Un evaluador puede reproducir cualquier vista.

**2. Un solo lenguaje (Python).** Servidor, reglas de negocio, informes y pruebas comparten lenguaje:
menos código duplicado entre «backend» y «frontend», y por tanto menos causas de error y correcciones
más rápidas. La lógica de autorización vive en el servidor, no en el navegador.

**3. SQLite embebido con migraciones versionadas (fastlite, apsw, fastmigrate).** Cero administración
de base de datos: instalación y respaldo simples, integridad transaccional y preservación verificable
de la evidencia. El volumen de una carrera y su instituto queda holgadamente dentro de su rango, sin
servidores adicionales que mantener.

**4. Accesibilidad y bajo costo de uso cotidiano.** Tablas con orden, filtro y «Descargar CSV»;
búsqueda global con `/`; **tema claro/oscuro**; diálogos con `role="dialog"` y foco gestionado; mensajes
de error con `role="alert"`; confirmación de lo irreversible y «Deshacer» en lo reversible. Todo esto
reduce el error humano, que es la principal amenaza a la calidad del dato de acreditación.

**5. Seguridad proporcional al dato personal.** CSP estricta sin recursos de terceros ni JavaScript en
línea, CSRF por `Origin` y cookies `SameSite`: la superficie de ataque es mínima y no se cargan recursos
de otros sitios. La privacidad se refleja en la interfaz: la fecha de nacimiento solo la ve la
administración y la propia persona; los informes usan **tramos de edad**; los adjuntos solo los ven
quienes editan.

**6. Recursos locales y versionados (Tailwind compilado, vendor con versión fija).** El sistema no
depende de CDNs ni de internet externo para funcionar: disponibilidad y control de versiones, importante
para la sostenibilidad de la evidencia en el tiempo.

**7. Trazabilidad como función de usuario, no solo de auditoría.** En el anexo I+D+i, **cada cifra es un
enlace a los registros que la componen** (qué artículos, qué personas, qué proyectos) con la regla
aplicada: se responde «¿de dónde sale este número?» en la propia interfaz. El catálogo de revistas
guarda **fuente y enlace de evidencia** de cada indexación; la memoria incluye una sección
«Datos y método».

## En términos de acreditación

Para un par evaluador, la consecuencia es que **la captura cotidiana de cada docente produce
directamente la evidencia**: no hay una etapa manual de recompilación ni de transcripción. La
combinación de rol acotado, validación en servidor, tablero de calidad de datos (16 revisiones con
enlace a la corrección) e informes imprimibles en A4 con membrete convierte el stack en un soporte de
**datos confiables, reproducibles y auditables**, que es exactamente lo que demanda un proceso de
autoevaluación y acreditación.

---

## Notas internas (no forman parte del informe)

- No se verificó conformidad formal con WCAG; la accesibilidad se describe como características
  concretas, no como certificación. Una prueba en Chrome revisa en cada cambio las pantallas principales (contraste,
  etiquetas, un solo encabezado principal; PLAN §62).
- Ante un par evaluador técnico, conviene añadir una línea con las versiones exactas (FastHTML 0.14,
  HTMX, Tailwind 3.4, SQLite) y el dato de la batería de pruebas (~1.060 pruebas y ~50 flujos en Chrome con
  Playwright) como evidencia de calidad de ingeniería.
