#!/bin/sh
# Arranque del contenedor de `agente-tutor`: aplica migraciones sobre la base
# SQLite del volumen (/app/data) y deja corriendo el comando recibido
# (gunicorn, ver Dockerfile).
set -e

python manage.py migrate --noinput

exec "$@"
