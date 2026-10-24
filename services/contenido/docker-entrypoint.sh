#!/bin/sh
# Arranque del contenedor de `contenido`: aplica migraciones, carga los
# caracteres si la base está vacía y deja corriendo el comando recibido
# (gunicorn, ver Dockerfile). Si migrate falla el arranque se detiene; si
# falla la descarga o la carga del dataset, queda un AVISO y Django arranca.
set -e

python manage.py migrate --noinput

# El dataset de Make Me a Hanzi no está en el repo (ver .gitignore): llega
# montado como volumen desde services/contenido/data_hanzi. Se acepta tanto
# el clon directo en esa carpeta como dentro de una subcarpeta makemeahanzi/.
DATOS=""
for ruta in /datos /datos/makemeahanzi; do
    if [ -f "$ruta/dictionary.txt" ] && [ -f "$ruta/graphics.txt" ]; then
        DATOS="$ruta"
        break
    fi
done

# Sin volumen (p. ej. una instancia nueva): se descarga del repositorio
# público, solo si la base está vacía.
if [ -z "$DATOS" ]; then
    python descargar_datos.py --destino /tmp/makemeahanzi
    if [ -f /tmp/makemeahanzi/dictionary.txt ] && [ -f /tmp/makemeahanzi/graphics.txt ]; then
        DATOS=/tmp/makemeahanzi
    fi
fi

if [ -n "$DATOS" ]; then
    # El shell termina con código 0 solo si todavía no hay caracteres.
    if python manage.py shell -c "import sys; from caracteres.models import Caracter; sys.exit(Caracter.objects.exists())"; then
        python manage.py cargar_hanzi --ruta "$DATOS" --nivel 1 2 3 4 5 6 \
            || echo "AVISO: falló la carga del dataset; contenido arranca con el catálogo vacío o incompleto."
    fi
else
    echo "Sin dataset en /datos ni descargado: no se importan caracteres."
fi

exec "$@"
