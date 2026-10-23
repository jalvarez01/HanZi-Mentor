#!/bin/sh
# Arranque del contenedor de catalogo-flask: crea la base si no existe, carga
# los caracteres si está vacía y deja corriendo el comando recibido (gunicorn,
# ver Dockerfile). Ningún paso previo detiene el arranque: si algo falla queda
# un AVISO en el log y /health informa el estado de la base.
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

python crear_base.py

# Sin volumen (p. ej. una instancia nueva): se descarga del repositorio
# público, solo si la base está vacía.
if [ -z "$DATOS" ]; then
    DESCARGA=/tmp/makemeahanzi
    python descargar_datos.py --destino "$DESCARGA"
    if [ -f "$DESCARGA/dictionary.txt" ] && [ -f "$DESCARGA/graphics.txt" ]; then
        DATOS="$DESCARGA"
    fi
fi

if [ -n "$DATOS" ]; then
    python cargar.py --ruta "$DATOS" --nivel 1 2 3 4 5 6 --si-vacia \
        || echo "AVISO: falló la carga del dataset; el catálogo arranca sin caracteres."
else
    echo "Sin dataset en /datos ni descargado: no se importan caracteres."
fi

exec "$@"
