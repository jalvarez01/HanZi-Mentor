"""Microservicio de suscripciones Free y Premium (RF-USR-01)."""

from flask import Flask, current_app, jsonify

import config
import modelos  # noqa: F401  (registra las tablas antes de iniciar_db)
from db import db_disponible, iniciar_db, usa_db
from dominio.suscripcion import ahora
from errores import registrar_manejadores
from i18n import iniciar_i18n
from pasarelas.fabrica import crear_pasarela
from rutas import suscripciones_bp


def create_app(config_extra=None):
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    app.config["RELOJ"] = ahora
    if config_extra:
        app.config.update(config_extra)

    # Las pruebas pueden pasar su propia pasarela en config["PASARELA"].
    app.extensions["pasarela"] = app.config.get("PASARELA") or crear_pasarela(
        app.config["PASARELA_PAGO"]
    )

    iniciar_db(app)
    iniciar_i18n(app)
    registrar_manejadores(app)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    app.register_blueprint(suscripciones_bp)

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
