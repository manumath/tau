# Gobernanza del sistema (PLAN §72, etapa 9)

Asuntos que no se resuelven con código y que conviene dejar acordados antes de abrir TAU a toda la Carrera. Cada punto
dice qué hay que decidir, con quién y en qué estado está. Cuando se resuelva, anote la decisión con fecha en PLAN.md.

## 1. Quién mantiene TAU

Lo mantienen la Dirección del Instituto de Investigación Matemática y su personal de TI, con la Dirección de Carrera. La
Administración del sistema gestiona cuentas, roles (a pedido de las direcciones) y la auditoría. La Dirección de Carrera es
la única que define categoría, vínculo y carga horaria. Estado: **vigente**.

## 2. Datos que TAU recibe de otros sistemas

TAU no reemplaza al sistema de Seguimiento Académico ni a Kardex: recibe de ellos exportaciones en CSV (cohortes y estados
de los estudiantes; rendimiento agregado por asignatura y gestión; listas de curso temporales).

- **Qué acordar con la DTIC:** el formato de cada exportación, quién la genera, con qué frecuencia y por qué canal llega
  (nunca por correo con datos personales sin cifrar). Que los agregados por asignatura lleguen ya sin RU ni notas.
- **Estado:** **por acordar.** Mientras tanto, Gestión de datos carga los archivos a mano.

## 3. Titularidad del software

El código es público en GitHub. Hay que precisar quién es el titular (la Universidad, la Facultad, la Carrera o sus
autores) y con qué licencia se publica.

- **Qué hacer:** consulta de la Dirección de Carrera a la instancia que corresponda de la Universidad.
- **Estado:** **por consultar.**

## 4. Dónde se alojan los datos de los estudiantes

Hoy el sistema puede alojarse en un servicio en la nube (Fly.io, con réplica en almacenamiento de objetos) o en un
servidor propio. Hay que verificar qué dice la Política de Tecnologías de la Información y Comunicación de la Universidad
sobre el alojamiento de datos personales de estudiantes fuera de sus servidores.

- **Alternativa si la política lo exige:** un servidor de la DTIC. TAU ya funciona en un servidor propio
  (`docs/despliegue.md`) y el paquete de datos (`scripts/paquete.py`) permite mudarse sin perder nada.
- **Estado:** **por verificar** antes de cargar datos reales de estudiantes.

## 5. Respaldo

Copia continua (Litestream) o diaria de la base, y un **simulacro de restauración** cada semestre y antes del piloto con
`scripts/restaurar_prueba.sh` (`docs/mantenimiento.md` §5.3). Responsable: TI del Instituto.

## 6. Privacidad

La página pública **Privacidad** (`/publico/privacidad`) dice qué datos guarda TAU, para qué, quién los ve y cuánto se
conservan, y cada formulario con datos personales lo resume junto al botón de enviar. La Dirección de Carrera revisa esos
textos antes del piloto y cada vez que cambie una regla. Los pedidos de corrección o eliminación de datos los atiende la
Dirección de Carrera.
