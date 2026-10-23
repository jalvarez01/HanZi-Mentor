"""Configuración del servicio, leída siempre de variables de entorno."""

import os

# Base local por defecto: un archivo SQLite junto al servicio. En Docker,
# docker-compose.yml define DATABASE_URL apuntando a PostgreSQL.
DATABASE_URL_LOCAL = "sqlite:///db.sqlite3"


def _booleano(nombre, defecto="0"):
    return os.environ.get(nombre, defecto).strip().lower() in ("1", "true", "si")


def desde_entorno():
    """Devuelve la configuración del servicio como dict para app.config.

    DATABASE_URL vacío ("") indica que el servicio no usa base de datos.
    """
    return {
        "SERVICE_NAME": os.environ.get("SERVICE_NAME", "catalogo-flask"),
        "HOST": os.environ.get("HOST", "0.0.0.0"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "FLASK_DEBUG": _booleano("FLASK_DEBUG"),
        "DATABASE_URL": os.environ.get("DATABASE_URL", DATABASE_URL_LOCAL) or None,
        "DB_CREAR_TABLAS": _booleano("DB_CREAR_TABLAS", "1"),
    }
