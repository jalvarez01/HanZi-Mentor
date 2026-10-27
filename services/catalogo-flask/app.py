"""Microservicio de catálogo: caracteres, trazos y lecciones (Strangler Pattern, T13)."""

from flask import Flask, current_app, jsonify

import config
import modelos  # noqa: F401  (registra las tablas antes de iniciar_db)
from db import db_disponible, iniciar_db, usa_db
from errores import registrar_manejadores
from i18n import iniciar_i18n
from rutas import catalogo_bp
from rutas_publico import publico_bp


def create_app(config_extra=None):
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if config_extra:
        app.config.update(config_extra)

    # `modelos` ya está importado arriba: iniciar_db crea sus tablas.
    iniciar_db(app)
    # Idioma de los mensajes según Accept-Language (es por defecto).
    iniciar_i18n(app)
    registrar_manejadores(app)
    # Igual que DRF en v1: hanzi como UTF-8 legible y claves en el orden
    # de los campos, no en orden alfabético.
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    app.register_blueprint(catalogo_bp)
    # Resumen para el equipo aliado (T14), con CORS abierto.
    app.register_blueprint(publico_bp)

    app.add_url_rule("/health", view_func=health, methods=["GET"])
    return app


def health():
    servicio = current_app.config["SERVICE_NAME"]
    if usa_db(current_app) and not db_disponible(current_app):
        return jsonify({
            "estado": "error",
            "servicio": servicio,
            "codigo": "DB_NO_DISPONIBLE",
        }), 503
    return jsonify({"estado": "ok", "servicio": servicio}), 200


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["FLASK_DEBUG"],
    )
