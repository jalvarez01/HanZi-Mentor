"""Microservicio de reportes asíncronos con Redis y Celery (T18 y T19)."""

import redis
from flask import Flask, current_app, jsonify

import config
from errores import registrar_manejadores, respuesta_error
from fabricas import crear_publicador, crear_redis
from i18n import iniciar_i18n, traducir
from mensajes import N_
from notificaciones import NotificacionesRedis
from rutas import reportes_bp


def create_app(config_extra=None, redis_cliente=None, notificaciones=None, publicador=None):
    """`redis_cliente`, `notificaciones` y `publicador` permiten inyectar
    dobles en las pruebas; si no se pasan, se crean con REDIS_URL. Las
    tareas se encolan con `publicador` y sus resultados se leen con
    `tareas.celery_app`."""
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if config_extra:
        app.config.update(config_extra)

    # Idioma de los mensajes según Accept-Language (es por defecto).
    iniciar_i18n(app)
    registrar_manejadores(app)
    # Hanzi como UTF-8 legible y claves en el orden en que se arman.
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    app.extensions["redis"] = redis_cliente or crear_redis(app.config)
    app.extensions["notificaciones"] = notificaciones or NotificacionesRedis(app.extensions["redis"])
    app.extensions["publicador"] = publicador or crear_publicador(app.config)

    app.register_blueprint(reportes_bp)

    app.add_url_rule("/health", view_func=health, methods=["GET"])
    return app


def health():
    """Sin Redis no se puede encolar ni consultar: el servicio no está sano."""
    try:
        current_app.extensions["redis"].ping()
    except (redis.RedisError, OSError):
        current_app.logger.warning("Redis no responde en /health")
        return respuesta_error(
            traducir(N_("La cola de tareas no está disponible.")), "COLA_NO_DISPONIBLE", 503
        )
    return jsonify({"estado": "ok", "servicio": current_app.config["SERVICE_NAME"]}), 200


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["FLASK_DEBUG"],
    )
