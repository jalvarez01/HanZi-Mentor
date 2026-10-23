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
        "SERVICE_NAME": os.environ.get("SERVICE_NAME", "sesiones-flask"),
        "HOST": os.environ.get("HOST", "0.0.0.0"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "FLASK_DEBUG": _booleano("FLASK_DEBUG"),
        "DATABASE_URL": os.environ.get("DATABASE_URL", DATABASE_URL_LOCAL) or None,
        "DB_CREAR_TABLAS": _booleano("DB_CREAR_TABLAS", "1"),
        # Servicios de los que depende, por HTTP. URL base sin /api/v2.
        "CATALOGO_URL": os.environ.get("CATALOGO_URL", "http://localhost:5081"),
        "PROGRESO_URL": os.environ.get("PROGRESO_URL", "http://localhost:5083"),
        # Segundos por petición y reintentos de los GET (ver clientes.py).
        "HTTP_TIMEOUT": float(os.environ.get("HTTP_TIMEOUT", "3")),
        "HTTP_REINTENTOS": int(os.environ.get("HTTP_REINTENTOS", "2")),
        # Implementaciones elegidas por las fábricas (ver fabricas.py).
        "TUTOR_ENGINE": os.environ.get("TUTOR_ENGINE", "MOCK").strip().upper(),
        "NOTIFICADOR": os.environ.get("NOTIFICADOR", "CONSOLE").strip().upper(),
    }
