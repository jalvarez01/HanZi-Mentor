"""Descarga el dataset de Make Me a Hanzi cuando no llega montado en /datos.

Lo llama docker-entrypoint.sh, después de las migraciones. Solo descarga si
la base no tiene caracteres: un reinicio con la base ya cargada no vuelve a
bajar nada. Usa urllib de la biblioteca estándar, así la imagen no necesita
curl ni wget. Misma lógica que services/catalogo-flask/descargar_datos.py.

Nunca falla: ante cualquier error deja un AVISO, borra lo descargado a medias
y termina con código 0 para que el servicio arranque igual (sin caracteres).

Uso:
    python descargar_datos.py --destino /tmp/makemeahanzi
"""

import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

URL_BASE = "https://raw.githubusercontent.com/skishore/makemeahanzi/master"
ARCHIVOS = ("dictionary.txt", "graphics.txt")
# Segundos de espera por cada lectura de la red y para la descarga completa.
TIMEOUT_LECTURA = 30
TIMEOUT_TOTAL = 300
BLOQUE = 64 * 1024


def _base_vacia():
    """True si la base de contenido no tiene caracteres."""
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from caracteres.models import Caracter

    return not Caracter.objects.exists()


def _descargar(url, destino, fin):
    """Baja `url` a `destino` pasando por un .part; devuelve los bytes escritos."""
    parcial = destino.with_name(destino.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_LECTURA) as respuesta, \
                parcial.open("wb") as archivo:
            while True:
                if time.monotonic() > fin:
                    raise TimeoutError(f"se superaron {TIMEOUT_TOTAL} s de descarga")
                bloque = respuesta.read(BLOQUE)
                if not bloque:
                    break
                archivo.write(bloque)
        parcial.replace(destino)
    finally:
        parcial.unlink(missing_ok=True)
    return destino.stat().st_size


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destino", required=True, help="Carpeta escribible.")
    destino = Path(parser.parse_args(argv).destino)

    if all((destino / nombre).is_file() for nombre in ARCHIVOS):
        print(f"El dataset ya está descargado en {destino}.")
        return 0

    try:
        if not _base_vacia():
            print("La base ya tiene caracteres: no se descarga el dataset.")
            return 0
    except Exception as error:
        print(f"AVISO: no se pudo consultar la base de contenido: {error}", file=sys.stderr)
        return 0

    print(f"Descargando Make Me a Hanzi desde {URL_BASE} ...")
    inicio = time.monotonic()
    fin = inicio + TIMEOUT_TOTAL
    try:
        destino.mkdir(parents=True, exist_ok=True)
        total = 0
        for nombre in ARCHIVOS:
            tamano = _descargar(f"{URL_BASE}/{nombre}", destino / nombre, fin)
            total += tamano
            print(f"  {nombre}: {tamano / 1_000_000:.1f} MB")
    except Exception as error:
        for nombre in ARCHIVOS:
            (destino / nombre).unlink(missing_ok=True)
        print(
            f"AVISO: falló la descarga del dataset ({error}); "
            "la base queda sin caracteres.",
            file=sys.stderr,
        )
        return 0

    print(f"Descarga completa: {total / 1_000_000:.1f} MB en {time.monotonic() - inicio:.1f} s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
