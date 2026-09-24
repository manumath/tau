#!/bin/sh
# Arranque del portal dentro del contenedor (Dockerfile).
#
# - Con LITESTREAM_REPLICA_URL (o BUCKET_NAME, que Fly.io define al crear un bucket Tigris):
#   si el volumen está vacío restaura la base desde la réplica, y luego ejecuta el portal bajo
#   «litestream replicate», que copia cada cambio de la base al almacenamiento de objetos.
# - Sin réplica: ejecuta el portal directamente (los datos quedan solo en el volumen).
set -e

mkdir -p "$(dirname "$PORTAL_DB")"

if [ -z "$PORTAL_SECRET_KEY" ]; then
  echo "AVISO: PORTAL_SECRET_KEY no está definida; las sesiones se cerrarán en cada despliegue." >&2
fi

# Detrás del proxy de Fly, uvicorn toma la IP y el esquema reales del cliente de las cabeceras
# X-Forwarded-*. Se confía en cualquier origen porque el tráfico solo llega por ese proxy.
# (Va como variable de entorno y no como opción, para que el «*» no lo expanda el shell.)
export FORWARDED_ALLOW_IPS="*"
PORTAL="uvicorn main:app --host 0.0.0.0 --port 8080 --proxy-headers"

if [ -z "$LITESTREAM_REPLICA_URL" ] && [ -n "$BUCKET_NAME" ]; then
  export LITESTREAM_REPLICA_URL="s3://${BUCKET_NAME}/portal.db?endpoint=fly.storage.tigris.dev&region=auto"
fi

if [ -n "$LITESTREAM_REPLICA_URL" ]; then
  # Litestream debe recibir el endpoint de Tigris por la URL, no por esta variable
  # (ver https://litestream.io/guides/tigris/); el portal no la usa.
  unset AWS_ENDPOINT_URL_S3
  litestream restore -if-db-not-exists -if-replica-exists "$PORTAL_DB"
  exec litestream replicate -exec "$PORTAL"
fi

exec $PORTAL
