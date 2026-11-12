"""Microservicio que consume al equipo aliado, VaultDrop (T26), con el patrón Adapter."""

from flask import Flask, current_app, jsonify

import config
from adaptadores.fabrica import crear_proveedor
from errores import registrar_manejadores
from i18n import iniciar_i18n
from rutas import aliado_bp
from servicio import CatalogoAliado


def create_app(config_extra=None, proveedor=None):
    """Crea la app. `proveedor` permite inyectar uno ya construido (pruebas);
    si no se pasa, la fábrica lo elige según ALIADO_PROVEEDOR."""
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if config_extra:
        app.config.update(config_extra)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    # Raíz de composición: el único punto donde se decide qué adaptador concreto se usa.
    app.extensions["catalogo_aliado"] = CatalogoAliado(proveedor or crear_proveedor(app.config))

    app.register_blueprint(aliado_bp)
    iniciar_i18n(app)
    registrar_manejadores(app)

    app.add_url_rule("/health", view_func=health, methods=["GET"])
    return app


def health():
    # No depende del aliado: si VaultDrop está caído, este servicio sigue sano
    # y responde con el respaldo o con 503 en sus rutas.
    return jsonify({"estado": "ok", "servicio": current_app.config["SERVICE_NAME"]}), 200


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["FLASK_DEBUG"],
    )
