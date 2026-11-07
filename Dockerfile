# Imagen de TAU, Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática (Fly.io u otro servicio de contenedores).
# Los datos (base SQLite, fotos, adjuntos) viven en un volumen montado en /data.
FROM python:3.13-slim

# uv, para instalar exactamente las versiones de uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

# Litestream: replica la base SQLite a un almacenamiento de objetos (Tigris en Fly.io, o S3).
# Se verifica el SHA-256 de lo descargado contra el checksums.txt de la versión: si el archivo cambiara en el
# origen, la construcción falla en vez de instalar otra cosa. Al cambiar de versión, actualice las tres líneas
# (docs/mantenimiento.md, «Actualizar Litestream»).
ARG LITESTREAM_VERSION=0.5.17
ARG LITESTREAM_SHA256_AMD64=cfb371176d164437ae869f8351cfde49bd1804ae71c61923f75c9cba9c9c006d
ARG LITESTREAM_SHA256_ARM64=f8ca4a050095c1efbda2c4365172e61bf9d955ea0d9ac42f448b52e51819baa5
ARG TARGETARCH
ADD https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-x86_64.tar.gz /tmp/litestream-amd64.tar.gz
ADD https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-arm64.tar.gz /tmp/litestream-arm64.tar.gz
RUN cd /tmp \
    && printf '%s  %s\n' "$LITESTREAM_SHA256_AMD64" litestream-amd64.tar.gz "$LITESTREAM_SHA256_ARM64" litestream-arm64.tar.gz \
       | sha256sum -c - \
    && tar -xzf /tmp/litestream-${TARGETARCH:-amd64}.tar.gz -C /usr/local/bin litestream \
    && rm /tmp/litestream-*.tar.gz && litestream version

# Datos de zonas horarias: el portal trabaja en la hora de La Paz (PORTAL_ZONA_HORARIA).
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PORTAL_DB=/data/portal.db

WORKDIR /app
# Primero las dependencias (capa que se reutiliza mientras uv.lock no cambie), luego el código.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN chmod +x scripts/iniciar.sh scripts/como-tau.sh

COPY litestream.yml /etc/litestream.yml

# El sistema corre como «tau», sin privilegios: el código y el entorno son de root (solo lectura para él) y
# solo escribe en el volumen de datos. iniciar.sh arranca como root solo para ajustar los permisos del volumen
# (los volúmenes creados antes eran de root) y enseguida deja de serlo (setpriv).
RUN groupadd --system --gid 1000 tau \
    && useradd --system --uid 1000 --gid tau --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin tau

EXPOSE 8080
CMD ["/app/scripts/iniciar.sh"]
