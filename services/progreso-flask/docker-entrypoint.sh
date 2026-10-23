#!/bin/sh
# Arranque del contenedor de progreso-flask: crea la base si no existe y deja
# corriendo el comando recibido (gunicorn, ver Dockerfile). Igual que en
# catalogo-flask, crear_base.py nunca detiene el arranque: si falla queda un
# AVISO en el log y /health informa el estado de la base.
set -e

python crear_base.py

# Las tablas se crean una vez acá y no en paralelo desde cada worker de
# gunicorn. Si la base no responde, create_app solo deja el error en el log.
python -c "from app import create_app; create_app()"

exec "$@"
