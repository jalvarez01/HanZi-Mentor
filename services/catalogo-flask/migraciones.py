"""Cambios de esquema sobre bases que ya existían.

`create_all` crea las tablas que faltan, pero no les agrega columnas nuevas.
Cada paso es idempotente: se puede correr en cada arranque y desde varios
procesos de gunicorn a la vez.
"""

from sqlalchemy import inspect, text


def agregar_lecturas(engine):
    """Columna caracteres.lecturas (JSON, nula hasta que se completa)."""
    if engine.dialect.name == "postgresql":
        # IF NOT EXISTS evita la carrera entre workers que arrancan a la vez.
        with engine.begin() as conexion:
            conexion.execute(text("ALTER TABLE caracteres ADD COLUMN IF NOT EXISTS lecturas JSON"))
        return
    columnas = {c["name"] for c in inspect(engine).get_columns("caracteres")}
    if "lecturas" not in columnas:
        with engine.begin() as conexion:
            conexion.execute(text("ALTER TABLE caracteres ADD COLUMN lecturas JSON"))


def migrar(app):
    """Aplica los pasos pendientes. Si la base no responde, /health lo informa."""
    if "db" not in app.extensions:
        return
    try:
        agregar_lecturas(app.extensions["db"]["engine"])
    except Exception:
        app.logger.exception("No se pudo migrar el esquema del catálogo")
