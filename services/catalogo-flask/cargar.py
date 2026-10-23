"""Carga el dataset de Make Me a Hanzi en la base propia del servicio.

Uso, desde services/catalogo-flask:
    python cargar.py --ruta ../contenido/data_hanzi --nivel 1 2
    python cargar.py --ruta ../contenido/data_hanzi --todos --limpiar

Usa la misma configuración que el servicio: DATABASE_URL (SQLite local
db.sqlite3 si no se define). Las tablas se crean si no existen.
"""

import argparse
import sys

from app import create_app
from carga import ErrorCarga, base_vacia, cargar


def _argumentos(argv):
    parser = argparse.ArgumentParser(
        description="Importa caracteres y trazos desde los datos de Make Me a Hanzi."
    )
    parser.add_argument(
        "--ruta", required=True,
        help="Carpeta que contiene dictionary.txt y graphics.txt.",
    )
    parser.add_argument(
        "--nivel", nargs="+", type=int, default=[1, 2],
        help="Niveles HSK a importar. Por defecto 1 y 2.",
    )
    parser.add_argument(
        "--todos", action="store_true",
        help=(
            "Importa TODOS los caracteres del archivo, no solo los de las listas "
            "HSK. Los que no estén en ninguna lista quedan con nivel_hsk vacío."
        ),
    )
    parser.add_argument(
        "--limpiar", action="store_true",
        help="Borra los caracteres existentes (y sus ejercicios) antes de importar.",
    )
    parser.add_argument(
        "--si-vacia", action="store_true",
        help="Solo importa si la base no tiene caracteres (lo usa el arranque en Docker).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    opciones = _argumentos(argv)
    app = create_app()
    sesion = app.extensions["db"]["fabrica"]()

    try:
        if opciones.si_vacia and not base_vacia(sesion):
            print("La base ya tiene caracteres: no se importa nada.")
            return 0

        if opciones.todos:
            print("Importando TODOS los caracteres del archivo...")
        else:
            print(f"Importando caracteres de HSK {opciones.nivel}...")

        resumen = cargar(
            sesion,
            opciones.ruta,
            niveles=opciones.nivel,
            todos=opciones.todos,
            limpiar=opciones.limpiar,
        )
    except ErrorCarga as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        sesion.close()

    if opciones.limpiar:
        print(f"Borrados {resumen.borrados} registros previos.")
    print(f"Listo: {resumen.creados} creados, {resumen.actualizados} actualizados.")
    print(f"Con nivel HSK asignado: {resumen.con_nivel}")
    if resumen.sin_nivel:
        print(f"Sin clasificar: {resumen.sin_nivel}")
    if resumen.sin_datos:
        print(
            f"Sin datos en la fuente ({len(resumen.sin_datos)}): "
            f"{''.join(resumen.sin_datos[:20])}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
