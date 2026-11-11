"""Microservicio de oraciones de ejemplo (API de terceros mediante el patrón Adapter)."""

from flask import Flask, current_app, jsonify

import config
from adaptadores.fabrica import crear_proveedor
from errores import registrar_manejadores
from i18n import iniciar_i18n
from rutas import ejemplos_bp


def create_app(config_extra=None, proveedor=None):
    """Crea la app. `proveedor` permite inyectar uno ya construido (pruebas);
    si no se pasa, la fábrica lo elige según PROVEEDOR_EJEMPLOS."""
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if config_extra:
        app.config.update(config_extra)
    # Los ejemplos van en chino: se responde UTF-8 legible en vez de \uXXXX.
    app.json.ensure_ascii = False

    # Raíz de composición: el único punto donde se decide qué adaptador concreto se usa.
    app.extensions["proveedor_ejemplos"] = proveedor or crear_proveedor(app.config)

    app.register_blueprint(ejemplos_bp)
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
