"""Base de datos propia del servicio con SQLAlchemy 2.x.

Cada petición usa su propia sesión: se abre la primera vez que se pide con
obtener_sesion() y se cierra al terminar la petición (rollback si hubo error).
"""

from flask import current_app, g
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Clase base de los modelos del servicio."""


def _crear_engine(url):
    opciones = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        opciones["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # En memoria cada conexión sería una base distinta: se comparte una.
            opciones["poolclass"] = StaticPool
    return create_engine(url, **opciones)


def iniciar_db(app):
    """Configura el engine y el cierre de sesiones. No hace nada sin DATABASE_URL."""
    url = app.config.get("DATABASE_URL")
    if not url:
        return

    engine = _crear_engine(url)
    app.extensions["db"] = {
        "engine": engine,
        "fabrica": sessionmaker(bind=engine, expire_on_commit=False),
    }

    if app.config.get("DB_CREAR_TABLAS"):
        try:
            Base.metadata.create_all(engine)
        except Exception:
            # El servicio arranca igual; /health informa que la base no responde.
            app.logger.exception("No se pudieron crear las tablas")

    @app.teardown_appcontext
    def cerrar_sesion(exc):
        sesion = g.pop("db_sesion", None)
        if sesion is not None:
            if exc is not None:
                sesion.rollback()
            sesion.close()


def usa_db(app):
    return "db" in app.extensions


def obtener_sesion():
    """Sesión de la petición actual."""
    if "db_sesion" not in g:
        g.db_sesion = current_app.extensions["db"]["fabrica"]()
    return g.db_sesion


def db_disponible(app):
    try:
        with app.extensions["db"]["engine"].connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except Exception:
        app.logger.exception("La base de datos no responde")
        return False
