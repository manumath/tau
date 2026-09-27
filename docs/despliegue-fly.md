# Despliegue en Fly.io

[Fly.io](https://fly.io) ejecuta el sistema como contenedor sin administrar un servidor: da HTTPS,
un volumen persistente para los datos y secretos para la configuración. Es una alternativa a la
[instalación en un servidor propio](despliegue.md); más abajo se explica cómo
[mudarse de una a otra](#mudarse-a-un-servidor-propio-sin-perder-nada) sin perder nada.

Archivos del proyecto que usa: `Dockerfile`, `fly.toml`, `litestream.yml` y `scripts/iniciar.sh`.

## Cómo queda armado

```
Usuarios ──HTTPS──▶ Fly.io ──▶ Máquina (1)  ── volumen /data: portal.db, fotos/, adjuntos/
                                   │
                                   └─ Litestream ──▶ Tigris (almacenamiento de objetos de Fly):
                                                     copia continua de portal.db
```

- **Una sola máquina**, siempre encendida (`fly.toml`). SQLite y el volumen no se comparten entre
  máquinas; para un instituto sobra.
- **Litestream** copia cada cambio de la base a Tigris. Si el volumen se perdiera, al arrancar se
  restaura sola desde ahí. Las **fotos y adjuntos no** van en esa copia: los cubren las
  instantáneas diarias del volumen que hace Fly y el [paquete de datos](#respaldos) que
  conviene descargar periódicamente.
- El correo sale por un **SMTP externo** (el del instituto u otro servicio): Fly no envía correo.

Costo: Fly cobra por uso (máquina, volumen, almacenamiento en Tigris). Para este tamaño debería
ser del orden de pocos dólares al mes; revise la tarifa vigente en su sitio.

## 1. Preparación (una vez)

1. Cree una cuenta en Fly.io e instale su herramienta de línea de comandos:
   ```bash
   brew install flyctl        # macOS; para otros sistemas vea fly.io/docs/flyctl/install
   fly auth login
   ```
2. En `fly.toml`, cambie `app` por un nombre libre y, si quiere, la región (`fly platform
   regions` las lista; `gru` = São Paulo es la más cercana en Sudamérica). Luego cree la app:
   ```bash
   fly apps create NOMBRE-DE-LA-APP
   ```
3. Cree el almacenamiento para la réplica de la base (Tigris) desde la carpeta del proyecto:
   ```bash
   fly storage create
   ```
   Deja definidos como secretos de la app `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y
   `BUCKET_NAME`, entre otros; `scripts/iniciar.sh` los usa para activar Litestream. Si no
   quedaran definidos, cópielos con `fly secrets set`.
4. Defina los secretos del sistema (una sola línea o varias):
   ```bash
   fly secrets set PORTAL_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
   fly secrets set PORTAL_URL=https://portal.iimat.umsa.bo PORTAL_INSTITUTO="Instituto de Investigación Matemática" \
                   PORTAL_CONTACTO=soporte@umsa.bo
   fly secrets set PORTAL_CORREO_REMITENTE="TAU <no-responder@umsa.bo>" \
                   PORTAL_SMTP_HOST=smtp.umsa.bo PORTAL_SMTP_PUERTO=587 \
                   PORTAL_SMTP_USUARIO=no-responder@umsa.bo PORTAL_SMTP_CLAVE='…'
   ```
   `PORTAL_SECRET_KEY` debe quedar fija: si cambia, se cierran todas las sesiones. Guárdela
   también en un lugar seguro: sirve para mudarse sin cerrar sesiones.

## 2. Desplegar

```bash
fly deploy
```

La primera vez crea el volumen `portal_datos` (3 GB, ampliable) y la base con todas las
migraciones. Luego cree el primer administrador:

```bash
fly ssh console
python /app/scripts/crear_admin.py   # dentro de la máquina
exit
```

**No use `scripts/seed.py`**: crea cuentas de demostración con contraseñas públicas.

## 3. Dominio propio (recomendado desde el primer día)

```bash
fly certs add portal.iimat.umsa.bo
```

Fly indica qué registros DNS crear. Con un dominio propio, **mudarse después es invisible para
los usuarios**: la dirección no cambia y los enlaces ya enviados por correo siguen sirviendo. Con
la dirección `NOMBRE.fly.dev`, en cambio, al mudarse habría que avisar la nueva dirección.
`PORTAL_URL` debe coincidir con la dirección que usen las personas (también la usa la protección
CSRF). Si además se entra por `NOMBRE.fly.dev`, agréguela con
`fly secrets set PORTAL_ORIGENES_EXTRA=https://NOMBRE.fly.dev`.

## 4. Operación diaria

| Tarea | Comando |
|---|---|
| Ver registros | `fly logs` |
| Estado de la máquina | `fly status` |
| Publicar una versión nueva | `fly deploy` (las migraciones se aplican solas al arrancar) |
| Entrar a la máquina | `fly ssh console` |
| Instantáneas del volumen | `fly volumes list` y `fly volumes snapshots list ID_DEL_VOLUMEN` |
| Cambiar un secreto | `fly secrets set NOMBRE=valor` (reinicia la máquina) |

## Respaldos

- **Automático:** la base se replica continuamente en Tigris, y Fly toma instantáneas diarias
  del volumen (base, fotos y adjuntos).
- **Paquete de datos (recomendado, p. ej. semanal):** un archivo con *todo* (base, fotos y
  adjuntos) guardado fuera de Fly:
  ```bash
  fly ssh console -C "python /app/scripts/paquete.py exportar /data/paquete.tar.gz"
  fly ssh sftp get /data/paquete.tar.gz ./portal-$(date +%F).tar.gz
  fly ssh console -C "rm /data/paquete.tar.gz"
  ```

## Mudarse a un servidor propio sin perder nada

Todo lo que el sistema sabe está en tres lugares del volumen: `portal.db`, `fotos/` y `adjuntos/`.
El **paquete de datos** (`scripts/paquete.py`) los lleva juntos en un archivo, con un manifiesto
que se verifica al importar. Se conservan cuentas (con sus contraseñas, que viajan como hash),
perfiles, productos, actividades, proyectos con sus propuestas y estados, adjuntos, fotos y
auditoría.

1. **Prepare el servidor** según la [guía de despliegue](despliegue.md), pasos 1, 2, 4 y 5 (sin
   crear administrador: vendrá en el paquete). Use la misma `PORTAL_SECRET_KEY` que en Fly si
   quiere que nadie tenga que volver a ingresar, y la misma `PORTAL_URL` si mantiene el dominio.
2. **Avise una ventana breve** (p. ej. 15 minutos fuera de horario) y ponga el sistema en Fly en
   **solo lectura**: las personas pueden consultar, pero nada cambia después de la copia.
   ```bash
   fly secrets set PORTAL_SOLO_LECTURA=1      # reinicia la máquina con el aviso de mantenimiento
   ```
3. **Exporte y descargue** el paquete:
   ```bash
   fly ssh console -C "python /app/scripts/paquete.py exportar /data/paquete.tar.gz"
   fly ssh sftp get /data/paquete.tar.gz ./portal-mudanza.tar.gz
   ```
4. **Importe en el servidor** (con el sistema detenido allí):
   ```bash
   cd /opt/portal && set -a && source /etc/portal.env && set +a
   uv run python scripts/paquete.py importar portal-mudanza.tar.gz
   sudo systemctl start portal
   ```
   El importador verifica la integridad y que los conteos coincidan con el manifiesto, y aplica
   migraciones si el código del servidor es más nuevo. Si no mantendrá el dominio, avise la
   dirección nueva.
5. **Cambie el DNS** del dominio para que apunte al servidor y verifique con la lista de la
   [guía de despliegue](despliegue.md#9-lista-de-verificación).
6. **Retire Fly solo cuando todo funcione**, y guarde el paquete como respaldo:
   `fly apps destroy NOMBRE-DE-LA-APP` elimina la app y su volumen (**es irreversible**), y
   `fly storage destroy NOMBRE-DEL-BUCKET` elimina la réplica en Tigris.

Si algo falla antes del paso 6, `fly secrets unset PORTAL_SOLO_LECTURA` devuelve el sistema en Fly
a la normalidad, tal como estaba. No use `fly scale count 0` para detenerlo: destruye la máquina,
y al volver a crearla Fly puede asignarle un volumen nuevo y vacío (se perderían fotos y adjuntos).

**El camino inverso** (de un servidor propio a Fly) también es posible con el mismo paquete, pero
requiere un paso extra: importar con la réplica de Litestream detenida y reiniciarla desde cero,
para que no se mezcle con su historial anterior. Si llegara a necesitarlo, conviene preparar y
probar ese procedimiento antes.
