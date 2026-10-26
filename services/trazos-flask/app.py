"""Microservicio de validación de trazos (Strangler Pattern, taller 02)."""

from flask import Flask, current_app, jsonify

import config
from errores import registrar_manejadores
from i18n import iniciar_i18n
from rutas import trazos_bp


def create_app(config_extra=None):
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if config_extra:
        app.config.update(config_extra)

    app.register_blueprint(trazos_bp)
    # Idioma de los mensajes según Accept-Language (es por defecto).
    iniciar_i18n(app)
    registrar_manejadores(app)

    app.add_url_rule("/health", view_func=health, methods=["GET"])
    return app


def health():
    return jsonify({"estado": "ok", "servicio": current_app.config["SERVICE_NAME"]}), 200


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["FLASK_DEBUG"],
    )
