# Despliegue en producción

> ¿Sin servidor propio? Vea la alternativa en [Fly.io](despliegue-fly.md). Los datos se pueden
> mudar después entre una y otra sin perder nada (ver [Mudanzas](#mudanzas-y-mantenimiento)).

Guía para instalar el portal en un servidor Linux (Ubuntu o Debian) con HTTPS. Supone un dominio,
por ejemplo `portal.iimat.umsa.bo`, que ya apunta al servidor, y una cuenta de correo SMTP para
los envíos.

## 1. Código y dependencias

Instale [uv](https://docs.astral.sh/uv/) y copie el proyecto al servidor, por ejemplo con `git
clone` o, desde un equipo de desarrollo:

```bash
rsync -av --exclude .venv --exclude data --exclude .sesskey ./ usuario@servidor:/opt/portal/
```

En el servidor:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd /opt/portal && uv sync --no-dev
```

## 2. Configuración

Cree `/etc/portal.env`, legible solo por el usuario que ejecutará el portal (`chmod 600`):

```ini
PORTAL_DB=/var/lib/portal/portal.db
PORTAL_URL=https://portal.iimat.umsa.bo
PORTAL_SECRET_KEY=<clave aleatoria, ver abajo>
PORTAL_HTTPS_ONLY=1
PORTAL_INSTITUTO=Instituto de Investigación Matemática
PORTAL_CONTACTO=soporte@umsa.bo

PORTAL_CORREO_MODO=smtp
PORTAL_CORREO_REMITENTE=Portal de Investigación <no-responder@umsa.bo>
PORTAL_SMTP_HOST=smtp.umsa.bo
PORTAL_SMTP_PUERTO=587
PORTAL_SMTP_USUARIO=no-responder@umsa.bo
PORTAL_SMTP_CLAVE=<contraseña SMTP>
PORTAL_SMTP_STARTTLS=1
```

Para la clave de sesión:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

| Variable | Por qué importa |
|---|---|
| `PORTAL_URL` | Con ella se arman los enlaces de los correos (recuperar contraseña, invitaciones, avisos). |
| `PORTAL_SECRET_KEY` | Firma la cookie de sesión. Si cambia, todas las sesiones se cierran. |
| `PORTAL_HTTPS_ONLY=1` | La cookie de sesión solo viaja por HTTPS. |
| `PORTAL_CONTACTO` | Crossref atiende mejor las consultas que se identifican. |

Las fotos, los adjuntos y (en modo `archivo`) los correos se guardan en carpetas junto a la base:
`/var/lib/portal/fotos`, `/var/lib/portal/adjuntos` y `/var/lib/portal/correos`.

## 3. Base de datos y primer administrador

```bash
sudo mkdir -p /var/lib/portal && sudo chown TU_USUARIO /var/lib/portal
cd /opt/portal && set -a && source /etc/portal.env && set +a
uv run python scripts/crear_admin.py
```

El script crea la base (aplica todas las migraciones) y pide los datos del administrador por
consola. **No use `scripts/seed.py` en producción:** crea cuentas de demostración con contraseñas
públicas.

## 4. Servicio

`/etc/systemd/system/portal.service`:

```ini
[Unit]
Description=Portal de Investigación
After=network.target

[Service]
User=TU_USUARIO
WorkingDirectory=/opt/portal
EnvironmentFile=/etc/portal.env
ExecStart=/home/TU_USUARIO/.local/bin/uv run uvicorn main:app --host 127.0.0.1 --port 5001
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now portal
journalctl -u portal -f        # registros del servicio
```

Use `uvicorn` directamente: `python main.py` es el modo de desarrollo, con recarga automática.
Con SQLite basta un proceso; el portal atiende sin problema a un instituto.

## 5. HTTPS con Caddy

Caddy obtiene y renueva el certificado solo. Instálelo (`sudo apt install caddy`) y configure
`/etc/caddy/Caddyfile`:

```
portal.iimat.umsa.bo {
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

Toda la información está en la base SQLite **y** en las carpetas de fotos y adjuntos. Respalde
ambas cosas. Por ejemplo, con `crontab -e`, una copia diaria a las 3:00:

```
0 3 * * * sqlite3 /var/lib/portal/portal.db ".backup /respaldos/portal-$(date +\%F).db" && rsync -a /var/lib/portal/fotos /var/lib/portal/adjuntos /respaldos/archivos/
```

`.backup` hace una copia consistente aunque el portal esté en uso. Guarde los respaldos fuera
del servidor y pruebe de vez en cuando que se pueden restaurar. Para respaldo continuo, considere
[Litestream](https://litestream.io).

**Respaldo completo en un solo archivo:** `scripts/paquete.py` junta la base, las fotos y los
adjuntos en un `.tar.gz` con un manifiesto verificable (se puede ejecutar con el portal en marcha):

```bash
cd /opt/portal && set -a && source /etc/portal.env && set +a
uv run python scripts/paquete.py exportar /respaldos/portal-$(date +%F).tar.gz
```

## Mudanzas y mantenimiento

El mismo paquete sirve para trasladar el portal a otro servidor (o a/desde [Fly.io](despliegue-fly.md)):
exportar en el origen, `uv run python scripts/paquete.py importar archivo.tar.gz` en el destino
(con el portal detenido). El importador verifica la integridad y los conteos, no borra datos
existentes (los mueve a `respaldo-previo-…` si se usa `--reemplazar`) y aplica las migraciones
pendientes.

Para que nada cambie después de la copia, active el **modo solo lectura**: agregue
`PORTAL_SOLO_LECTURA=1` a `/etc/portal.env` y reinicie el servicio. Las personas pueden seguir
consultando, ven un aviso de mantenimiento, y cualquier cambio se rechaza con un mensaje claro.
Quite la variable y reinicie para volver a la normalidad.

## 8. Actualizar a una versión nueva

1. Respalde la base (paso 7).
2. Copie el código nuevo (`git pull` o `rsync`) y ejecute `uv sync --no-dev`.
3. `sudo systemctl restart portal`.

Las migraciones pendientes se aplican solas al arrancar. Nunca edite una migración ya aplicada:
los cambios de esquema van en un archivo nuevo en `migrations/`.

## 9. Lista de verificación

- [ ] `https://portal.iimat.umsa.bo` abre el ingreso con candado válido.
- [ ] El administrador ingresa y ve «Usuarios».
- [ ] «¿Olvidó su contraseña?» con una cuenta real hace llegar el correo, y el enlace apunta a
      `PORTAL_URL`.
- [ ] Se sube una foto de perfil y un adjunto PDF, y se descargan.
- [ ] La importación por DOI funciona (el servidor necesita salida a `api.crossref.org` y
      `export.arxiv.org`).
- [ ] El respaldo nocturno se genera, y una restauración de prueba funciona.
- [ ] `PORTAL_HTTPS_ONLY=1` y `PORTAL_SECRET_KEY` están definidos; `/etc/portal.env` tiene permisos 600.

## Pendiente recomendado antes del piloto

Hoy Tailwind, FrankenUI, htmx y KaTeX se cargan desde CDN. Funciona, pero conviene servirlos
desde el propio servidor (Tailwind compilado con su CLI), para no depender de terceros ni de
la conexión de cada usuario a esos servicios.
