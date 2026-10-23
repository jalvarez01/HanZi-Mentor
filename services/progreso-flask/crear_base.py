"""Crea la base de datos del progreso en PostgreSQL si todavía no existe.

Mismo script que services/catalogo-flask/crear_base.py (esquema del equipo:
un solo PostgreSQL `db` y una base por servicio).

Lo llama docker-entrypoint.sh en cada arranque. Es idempotente: sirve igual
sobre un volumen de PostgreSQL ya existente que sobre uno nuevo, donde los
scripts de /docker-entrypoint-initdb.d no vuelven a ejecutarse.

Solo actúa con URLs postgresql; con SQLite o sin DATABASE_URL no hace nada.
Nunca falla: si no puede crear la base deja un AVISO y termina con código 0,
y /health informa que la base no responde.
"""

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import config


def main():
    url = config.desde_entorno()["DATABASE_URL"]
    if not url or not url.startswith("postgresql"):
        return 0

    destino = make_url(url)
    nombre = destino.database
    # CREATE DATABASE no puede ir dentro de una transacción: se usa AUTOCOMMIT
    # sobre la base de mantenimiento `postgres`, que siempre existe.
    engine = create_engine(
        destino.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with engine.connect() as conexion:
            existe = conexion.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :nombre"),
                {"nombre": nombre},
            )
            if existe:
                print(f"La base {nombre} ya existe.")
                return 0
            nombre_seguro = engine.dialect.identifier_preparer.quote(nombre)
            conexion.execute(text(f"CREATE DATABASE {nombre_seguro}"))
            print(f"Base {nombre} creada.")
    except Exception as error:
        print(f"AVISO: no se pudo crear la base {nombre}: {error}", file=sys.stderr)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
