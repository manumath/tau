# Imagen de TAU, Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática (Fly.io u otro servicio de contenedores).
# Los datos (base SQLite, fotos, adjuntos) viven en un volumen montado en /data.
FROM python:3.13-slim

# uv, para instalar exactamente las versiones de uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

# Litestream: replica la base SQLite a un almacenamiento de objetos (Tigris en Fly.io, o S3).
ARG LITESTREAM_VERSION=0.5.17
ARG TARGETARCH
ADD https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-x86_64.tar.gz /tmp/litestream-amd64.tar.gz
ADD https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-arm64.tar.gz /tmp/litestream-arm64.tar.gz
RUN tar -xzf /tmp/litestream-${TARGETARCH:-amd64}.tar.gz -C /usr/local/bin litestream \
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
RUN chmod +x scripts/iniciar.sh

COPY litestream.yml /etc/litestream.yml

EXPOSE 8080
CMD ["/app/scripts/iniciar.sh"]
