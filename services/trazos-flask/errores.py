"""Manejadores globales: toda respuesta de error es JSON, nunca HTML."""

from flask import jsonify
from werkzeug.exceptions import HTTPException

from validacion import EntradaInvalida

_CODIGOS_HTTP = {
    400: "ENTRADA_INVALIDA",
    404: "NO_ENCONTRADO",
    405: "METODO_NO_PERMITIDO",
    500: "ERROR_INTERNO",
}


def _error(mensaje, codigo, estado):
    return jsonify({"error": mensaje, "codigo": codigo}), estado


def registrar_manejadores(app):
    @app.errorhandler(EntradaInvalida)
    def entrada_invalida(exc):
        return _error(str(exc), "ENTRADA_INVALIDA", 400)

    @app.errorhandler(400)
    def solicitud_incorrecta(exc):
        return _error("Solicitud incorrecta", "ENTRADA_INVALIDA", 400)

    @app.errorhandler(404)
    def no_encontrado(exc):
        return _error("Recurso no encontrado", "NO_ENCONTRADO", 404)

    @app.errorhandler(405)
    def metodo_no_permitido(exc):
        return _error("Método no permitido", "METODO_NO_PERMITIDO", 405)

    @app.errorhandler(500)
    def error_interno(exc):
        return _error("Error interno", "ERROR_INTERNO", 500)

    @app.errorhandler(Exception)
    def inesperado(exc):
        # Otros errores HTTP (p. ej. 413) conservan su estado, pero en JSON.
        if isinstance(exc, HTTPException):
            codigo = _CODIGOS_HTTP.get(exc.code, "ERROR_HTTP")
            return _error(exc.name, codigo, exc.code)
        # El detalle va al log del servidor, nunca al cliente.
        app.logger.exception("Error inesperado")
        return _error("Error interno", "ERROR_INTERNO", 500)
