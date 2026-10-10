"""Microservicio de validación de trazos (Strangler Pattern, taller 02)."""

import os

from flask import Flask, jsonify

NOMBRE_SERVICIO = "trazos-flask"


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_PUNTOS=int(os.environ.get("MAX_PUNTOS", "5000")),
    )
    if config:
        app.config.update(config)

    @app.get("/health")
    def health():
        return jsonify({"estado": "ok", "servicio": NOMBRE_SERVICIO}), 200

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
