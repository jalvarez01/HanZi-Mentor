"""Cambios de esquema sobre tablas que ya existen.

Mismo patrón que services/progreso-flask/migraciones.py: `create_all` crea
las tablas que faltan pero no toca una tabla existente, así que una base con
datos necesita un ALTER explícito. `aplicar()` agrega las columnas que
falten y no hace nada si ya están; la llama db.iniciar_db después de
create_all, en cada arranque.

RF-IA-02 agrega `ejercicios.codigo_error`: el tipo de error de un ejercicio
fallado, que se manda a progreso-flask al cerrar la sesión para calcular la
curva de olvido. Admite NULL (un acierto, o un fallo sin código), así que
las filas que ya existen quedan con NULL y no se reescribe la tabla.
modelos.py declara la misma columna: una base nueva y una migrada tienen el
mismo esquema.
"""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

# (tabla, columna, tipo SQL). Todas admiten NULL y no llevan valor por defecto.
COLUMNAS_NUEVAS = (
    ("ejercicios", "codigo_error", "VARCHAR(40)"),
    # RF-IA-03: el patrón de error que originó un ejercicio adaptado.
    ("ejercicios", "patron", "VARCHAR(40)"),
)


def columnas_faltantes(engine):
    inspector = inspect(engine)
    faltan = []
    for tabla, columna, tipo in COLUMNAS_NUEVAS:
        if not inspector.has_table(tabla):
            continue
        existentes = {c["name"] for c in inspector.get_columns(tabla)}
        if columna not in existentes:
            faltan.append((tabla, columna, tipo))
    return faltan


def aplicar(engine):
    """Agrega las columnas que falten. Devuelve "tabla.columna" de las que agregó."""
    faltan = columnas_faltantes(engine)
    if not faltan:
        return []

    # Dos workers pueden arrancar a la vez: en PostgreSQL, IF NOT EXISTS hace
    # que el segundo no falle. SQLite no lo admite y no tiene ese problema.
    si_falta = "IF NOT EXISTS " if engine.dialect.name == "postgresql" else ""
    with engine.begin() as conexion:
        for tabla, columna, tipo in faltan:
            conexion.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {si_falta}{columna} {tipo}"))

    agregadas = [f"{tabla}.{columna}" for tabla, columna, _ in faltan]
    logger.info("Migración: columnas agregadas %s", agregadas)
    return agregadas
