"""Microservicio de evaluación de respuestas (Strangler Pattern, T10)."""

from flask import Flask, current_app, jsonify

import config
from errores import registrar_manejadores
from fabricas import crear_dependencias
from i18n import iniciar_i18n
from rutas import evaluacion_bp


def create_app(config_extra=None, dependencias=None):
    """`dependencias` permite inyectar dobles en las pruebas; si no se pasa,
    fabricas.py las arma según la configuración."""
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if config_extra:
        app.config.update(config_extra)

    # Idioma de los mensajes según Accept-Language (es por defecto).
    iniciar_i18n(app)
    registrar_manejadores(app)
    # Hanzi como UTF-8 legible y claves en el orden en que se arman, como v1.
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    # Raíz de composición: el único lugar que decide qué implementaciones se usan.
    app.extensions["dependencias"] = dependencias or crear_dependencias(app.config)

    app.register_blueprint(evaluacion_bp)

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
