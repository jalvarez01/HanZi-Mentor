"""Cambios de esquema sobre tablas que ya existen.

`create_all` crea las tablas que faltan, pero no toca una tabla existente:
una base con datos necesita un ALTER explícito. `aplicar()` agrega las
columnas que falten y no hace nada si ya están, así que se puede ejecutar
en cada arranque (lo llama db.iniciar_db después de create_all).

Las columnas se agregan con NOT NULL y un valor por defecto en la base:
- las filas que ya existen toman ese valor y no se pierde ningún dato (en
  PostgreSQL 11 o superior no se reescribe la tabla);
- una imagen anterior del servicio, que no conoce las columnas, puede
  seguir insertando filas si hay que volver atrás.

modelos.py declara el mismo valor con `server_default`, para que una base
nueva (create_all) y una migrada queden con el mismo esquema.
"""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

TABLA = "progresos"

# (columna, tipo SQL, valor por defecto). RF-IA-01.
COLUMNAS_NUEVAS = (
    ("errores_por_codigo", "JSON", "'{}'"),
    ("historial_errores", "JSON", "'[]'"),
)


def columnas_faltantes(engine):
    inspector = inspect(engine)
    if not inspector.has_table(TABLA):
        return []
    existentes = {columna["name"] for columna in inspector.get_columns(TABLA)}
    return [c for c in COLUMNAS_NUEVAS if c[0] not in existentes]


def aplicar(engine):
    """Agrega las columnas que falten. Devuelve los nombres de las que agregó."""
    faltan = columnas_faltantes(engine)
    if not faltan:
        return []

    # Dos workers pueden arrancar a la vez: en PostgreSQL, IF NOT EXISTS hace
    # que el segundo no falle. SQLite no lo admite y no tiene ese problema.
    si_falta = "IF NOT EXISTS " if engine.dialect.name == "postgresql" else ""
    with engine.begin() as conexion:
        for nombre, tipo, defecto in faltan:
            conexion.execute(text(
                f"ALTER TABLE {TABLA} ADD COLUMN {si_falta}{nombre} {tipo} "
                f"NOT NULL DEFAULT {defecto}"
            ))

    agregadas = [nombre for nombre, _, _ in faltan]
    logger.info("Migración de %s: columnas agregadas %s", TABLA, agregadas)
    return agregadas
