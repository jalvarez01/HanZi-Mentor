#!/bin/sh
# Arranque del contenedor de catalogo-flask: carga los caracteres si la base
# está vacía y deja corriendo el comando recibido (gunicorn, ver Dockerfile).
set -e

# El dataset de Make Me a Hanzi no está en el repo: llega montado como
# volumen en /datos. Se acepta el clon directo o una subcarpeta makemeahanzi/.
DATOS=""
for ruta in /datos /datos/makemeahanzi; do
    if [ -f "$ruta/dictionary.txt" ] && [ -f "$ruta/graphics.txt" ]; then
        DATOS="$ruta"
        break
    fi
done

if [ -n "$DATOS" ]; then
    python cargar.py --ruta "$DATOS" --nivel 1 2 3 4 5 6 --si-vacia
else
    echo "AVISO: no se encontró el dataset en /datos; la base queda sin caracteres."
fi

exec "$@"
