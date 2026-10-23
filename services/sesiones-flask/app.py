"""Microservicio de sesiones de estudio adaptativas (Strangler Pattern, T12)."""

from flask import Flask, current_app, jsonify

import config
import modelos  # noqa: F401  (registra las tablas antes de iniciar_db)
from db import db_disponible, iniciar_db, usa_db
from errores import registrar_manejadores
from fabricas import crear_dependencias
from rutas import sesiones_bp


def create_app(config_extra=None, dependencias=None):
    """`dependencias` permite inyectar dobles en las pruebas; si no se pasa,
    fabricas.py las arma según la configuración."""
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if config_extra:
        app.config.update(config_extra)

    # `modelos` ya está importado arriba: iniciar_db crea sus tablas.
    iniciar_db(app)
    registrar_manejadores(app)
    # Igual que DRF en v1: hanzi como UTF-8 legible y claves en el orden de
    # los campos, no en orden alfabético.
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    # Raíz de composición: el único lugar que decide qué implementaciones se usan.
    app.extensions["dependencias"] = dependencias or crear_dependencias(app.config)

    app.register_blueprint(sesiones_bp)

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
