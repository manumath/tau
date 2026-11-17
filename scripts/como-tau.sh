#!/bin/sh
# Ejecuta un comando como el usuario «tau» dentro del contenedor (Dockerfile), para que lo que escriba en el
# volumen de datos quede con el dueño correcto. «fly ssh console» entra como root:
#
#   fly ssh console -C "/app/scripts/como-tau.sh python /app/scripts/paquete.py exportar /data/paquete.tar.gz"
set -e
exec setpriv --reuid=tau --regid=tau --init-groups "$@"
