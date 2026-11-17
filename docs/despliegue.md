# Despliegue en producción

> ¿Sin servidor propio? Vea la alternativa en [Fly.io](despliegue-fly.md). Los datos se pueden
> mudar después entre una y otra sin perder nada (ver [Mudanzas](#mudanzas-y-mantenimiento)).

Guía para instalar el sistema en un servidor Linux (Ubuntu o Debian) con HTTPS. Supone un dominio,
por ejemplo `tau.universidad.example`, que ya apunta al servidor, y una cuenta de correo SMTP para
los envíos.

## 1. Código y dependencias

Instale [uv](https://docs.astral.sh/uv/) y copie el proyecto al servidor, por ejemplo con `git
clone` o, desde un equipo de desarrollo:

```bash
rsync -av --exclude .venv --exclude data --exclude .sesskey ./ usuario@servidor:/opt/tau/
```

En el servidor:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd /opt/tau && uv sync --no-dev
```

## 2. Configuración

Cree `/etc/tau.env`, legible solo por el usuario que ejecutará el sistema (`chmod 600`):

```ini
TAU_DB=/var/lib/tau/tau.db
TAU_URL=https://tau.universidad.example
TAU_SECRET_KEY=<clave aleatoria, ver abajo>
TAU_HTTPS_ONLY=1
TAU_INSTITUTO=Instituto de Investigación Matemática
TAU_CONTACTO=soporte@universidad.example

TAU_CORREO_MODO=smtp
TAU_CORREO_REMITENTE=TAU <no-responder@universidad.example>
TAU_SMTP_HOST=smtp.universidad.example
TAU_SMTP_PUERTO=587
TAU_SMTP_USUARIO=no-responder@universidad.example
TAU_SMTP_CLAVE=<contraseña SMTP>
TAU_SMTP_STARTTLS=1
```

Para la clave de sesión:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

| Variable | Por qué importa |
|---|---|
| `TAU_URL` | Con ella se arman los enlaces de los correos (recuperar contraseña, invitaciones, avisos). También es un origen aceptado por la protección CSRF. |
| `TAU_ORIGENES_EXTRA` | Solo si el sistema se usa también desde otra dirección (p. ej. una IP interna): lista separada por comas. Si no, los cambios hechos desde esa dirección se rechazan con «Solicitud rechazada: no proviene del sistema». |
| `TAU_SECRET_KEY` | Firma la cookie de sesión. Si cambia, todas las sesiones se cierran. |
| `TAU_HTTPS_ONLY=1` | La cookie de sesión solo viaja por HTTPS. |
| `TAU_CONTACTO` | Crossref atiende mejor las consultas que se identifican. |

Las fotos, los adjuntos, los archivos de las evidencias de calidad, los registros y (en modo `archivo`) los correos se
guardan en carpetas junto a la base: `/var/lib/tau/fotos`, `adjuntos`, `evidencias`, `registros` y `correos`.

Variables que conviene revisar también: `TAU_DIRECCION` (pie del membrete), `TAU_AVISO_ERRORES` (aviso por correo
de cada error) y, durante el piloto, `TAU_PILOTO=1` (`docs/piloto.md`). La lista completa está en el README.

## 3. Instancia, base de datos y primer administrador

El sistema no trae los datos de ninguna unidad: los pone su **instancia**, una carpeta con las unidades, la marca, los
planes de estudio, el marco de calidad y los catálogos (PLAN §74). El repositorio trae dos:
`instancias/ejemplo` (una carrera ficticia y chica, para probar o para copiar). La de la Carrera de Matemática no está
en el repositorio público.

**1. Arme la instancia de su unidad.** Copie `instancias/ejemplo` a una carpeta **fuera del repositorio** y cámbiela:

| Archivo | Qué lleva |
|---|---|
| `instancia.toml` | `nombre`, `perfil` (módulos con que arranca) y `departamento_propio` (prefijo de las siglas de sus asignaturas) |
| `unidades.csv` | Sigla y nombre de la universidad, la facultad, la carrera y el instituto |
| `catalogos/areas.csv`, `lineas.csv` | Áreas y líneas de investigación. `MSC2020.tsv` solo si la unidad clasifica con MSC |
| `planes/` | `planes.csv` y un CSV por plan (formato en `instancias/ejemplo/planes/README.md`). Opcional |
| `calidad/marco-carrera/` | Marco de calidad en CSV. Opcional; `calidad/plan-de-mejora.csv` se sube después en pantalla |
| `marca/` | `marca.toml` con los colores y las imágenes con los nombres de `static/img/marca/`. Opcional: sin ella rige la marca genérica |

**2. Cree la base con la instancia y el primer administrador:**

```bash
sudo mkdir -p /var/lib/tau && sudo chown TU_USUARIO /var/lib/tau
cd /opt/tau && set -a && source /etc/tau.env && set +a     # con TAU_INSTANCIA=/ruta/a/su/instancia
uv run python scripts/instalar.py
uv run python scripts/crear_admin.py
```

`instalar.py` aplica el esquema, carga la instancia y deja activos los módulos de su perfil; sobre una base que ya tiene
cuentas se niega. `TAU_INSTANCIA` debe quedar en el entorno del servicio: de ahí salen la marca y los parámetros de
la unidad mientras el sistema corre. En el contenedor (`scripts/iniciar.sh`), si no hay base ni réplica que restaurar y
`TAU_INSTANCIA` está definida, la carga se hace sola en el primer arranque. **No use `scripts/seed.py` en
producción:** crea cuentas de demostración con contraseñas públicas.

### Módulos de la instalación

Una base **nueva** arranca con el `perfil` de su instancia (o con `TAU_PERFIL`, si está) y después manda
**Administración → Módulos** (PLAN §73). En una base que ya está en uso no tienen efecto.

| Perfil | Módulos activos al crear la base |
|---|---|
| `minimo` (por defecto) | Solo la plataforma (cuentas, roles, vínculos, avisos, auditoría) y los comunicados |
| `instituto` | Investigación, informes de investigación y comunicados |
| `carrera` | Planes de estudio, oferta y asignación docente, seguimiento estudiantil y comunicados |
| `carrera_instituto` | Los dos anteriores |
| `completo` | Todos |

Las siglas y los nombres de las unidades se pueden cambiar después en **Administración → Unidades** (o, sin una cuenta,
con `uv run python scripts/unidades.py carrera INF "Carrera de Informática"`). De ahí salen los nombres de los
membretes, las páginas públicas y los correos; `TAU_UNIVERSIDAD`, `TAU_FACULTAD`, `TAU_CARRERA` y
`TAU_INSTITUTO` solo hacen falta para imponer otro nombre.

Tras ingresar, el inicio muestra «Primeros pasos»: elegir los módulos, crear las cuentas y asignar el rol de Dirección
de Carrera. Activar un módulo trae los que necesita; apagar uno oculta sus pantallas y detiene sus avisos, pero no borra
datos. Cada unidad instala su propia copia, con su propia base: el sistema no comparte una base entre unidades.

## 4. Servicio

`/etc/systemd/system/tau.service`:

```ini
[Unit]
Description=TAU - Sistema Integrado de Gestión Académica y Científica (CMAT)
After=network.target

[Service]
User=TU_USUARIO
WorkingDirectory=/opt/tau
EnvironmentFile=/etc/tau.env
ExecStart=/home/TU_USUARIO/.local/bin/uv run uvicorn main:app --host 127.0.0.1 --port 5001 --no-access-log
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now tau
journalctl -u portal -f        # registros del servicio
```

Los registros del sistema también quedan en `data/registros/tau.log` (rotan a los 10 MB; se guardan 5
archivos): una línea por petición y, en los errores, la traza con su **código de referencia** (el que ve
el usuario en la página de error). `--no-access-log` evita que uvicorn duplique cada línea (y que anote la
consulta de las búsquedas, que puede traer nombres). Para recibir un correo cuando ocurra un error, defina
`TAU_AVISO_ERRORES` en `/etc/tau.env`. El chequeo de salud es `GET /salud` (responde `ok` si la base
contesta).

Use `uvicorn` directamente: `python main.py` es el modo de desarrollo, con recarga automática.
Con SQLite basta un proceso; el sistema atiende sin problema a un instituto.

## 5. HTTPS con Caddy

Caddy obtiene y renueva el certificado solo. Instálelo (`sudo apt install caddy`) y configure
`/etc/caddy/Caddyfile`:

```
tau.universidad.example {
    reverse_proxy 127.0.0.1:5001
    request_body {
        max_size 25MB      # adjuntos de hasta 20 MB
    }
}
```

```bash
sudo systemctl reload caddy
```

## 6. Cuentas del instituto

Ingrese como administrador y, en **Usuarios → Importar CSV**, suba la planilla de investigadores
(hay una plantilla descargable). Con **«Enviar invitaciones por correo»** cada persona recibe un
enlace para definir su contraseña; nadie más la conoce. Vea la [guía de uso](guia-de-uso.md#administración).

## 7. Respaldos

Toda la información está en la base SQLite **y** en las carpetas de fotos, adjuntos y evidencias. Respalde
todo. Por ejemplo, con `crontab -e`, una copia diaria a las 3:00:

```
0 3 * * * sqlite3 /var/lib/tau/tau.db ".backup /respaldos/tau-$(date +\%F).db" && rsync -a /var/lib/tau/fotos /var/lib/tau/adjuntos /var/lib/tau/evidencias /respaldos/archivos/
```

`.backup` hace una copia consistente aunque el sistema esté en uso. Guarde los respaldos fuera
del servidor y compruebe cada semestre que se pueden restaurar con `scripts/restaurar_prueba.sh`
(`docs/mantenimiento.md` §5.3). Para respaldo continuo, considere [Litestream](https://litestream.io).

**Respaldo completo en un solo archivo:** `scripts/paquete.py` junta la base, las fotos, los adjuntos y
los archivos de las evidencias en un `.tar.gz` con un manifiesto verificable (se puede ejecutar con el sistema en marcha):

```bash
cd /opt/tau && set -a && source /etc/tau.env && set +a
uv run python scripts/paquete.py exportar /respaldos/tau-$(date +%F).tar.gz
```

## Mudanzas y mantenimiento

El mismo paquete sirve para trasladar el sistema a otro servidor (o a/desde [Fly.io](despliegue-fly.md)):
exportar en el origen, `uv run python scripts/paquete.py importar archivo.tar.gz` en el destino
(con el sistema detenido). El importador verifica la integridad y los conteos, no borra datos
existentes (los mueve a `respaldo-previo-…` si se usa `--reemplazar`) y aplica las migraciones
pendientes.

Para que nada cambie después de la copia, active el **modo solo lectura**: agregue
`TAU_SOLO_LECTURA=1` a `/etc/tau.env` y reinicie el servicio. Las personas pueden seguir
consultando, ven un aviso de mantenimiento, y cualquier cambio se rechaza con un mensaje claro.
Quite la variable y reinicie para volver a la normalidad.

## 8. Actualizar a una versión nueva

1. Respalde la base (paso 7).
2. Copie el código nuevo (`git pull` o `rsync`) y ejecute `uv sync --no-dev`.
3. `sudo systemctl restart tau`.

Las migraciones pendientes se aplican solas al arrancar. Nunca edite una migración ya aplicada:
los cambios de esquema van en un archivo nuevo en `migrations/`.

## 9. Lista de verificación

- [ ] `https://tau.universidad.example` abre el ingreso con candado válido.
- [ ] El administrador ingresa y ve «Usuarios».
- [ ] «¿Olvidó su contraseña?» con una cuenta real hace llegar el correo, y el enlace apunta a
      `TAU_URL`.
- [ ] Se sube una foto de perfil y un adjunto PDF, y se descargan.
- [ ] Guardar cualquier cambio (p. ej. el perfil) funciona. Si aparece «Solicitud rechazada: no
      proviene del sistema», el proxy no está conservando el encabezado `Host` o se entra por una
      dirección distinta de `TAU_URL` (agréguela a `TAU_ORIGENES_EXTRA`).
- [ ] La importación por DOI funciona (el servidor necesita salida a `api.crossref.org`,
      `export.arxiv.org`, `api.zbmath.org` y, para la producción y las citas, `api.openalex.org`).
- [ ] El respaldo nocturno se genera, y una restauración de prueba funciona.
- [ ] `TAU_HTTPS_ONLY=1` y `TAU_SECRET_KEY` están definidos; `/etc/tau.env` tiene permisos 600.

## Recursos de las páginas y política de contenido

Desde el 26 de septiembre de 2026 las páginas no dependen de ningún CDN: htmx, Franken UI, KaTeX
y los estilos de Tailwind (ya compilados) se sirven desde `/static` del propio sistema, con versión
por contenido y caché de un año. Cada respuesta lleva una política de seguridad de contenido (CSP)
que solo admite recursos del sistema. Si un proxy inverso agrega su propia CSP, no debe ser más
permisiva; si agrega otra más estricta, compruebe que las páginas siguen funcionando.
