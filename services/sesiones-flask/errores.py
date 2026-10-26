"""Manejadores globales: toda respuesta de error es JSON, nunca HTML."""

from flask import jsonify
from werkzeug.exceptions import HTTPException

from dominio.excepciones import DominioError
from i18n import traducir
from mensajes import N_

_CODIGOS_HTTP = {
    400: "ENTRADA_INVALIDA",
    404: "NO_ENCONTRADO",
    405: "METODO_NO_PERMITIDO",
    500: "ERROR_INTERNO",
}


class ErrorDominio(Exception):
    """Regla de negocio incumplida. Se responde con su estado y código, 400 por defecto.

    `mensaje` es el texto en español marcado con N_ y `params` completa sus
    marcadores (`%(nombre)s`). Se traduce al responder, según Accept-Language.
    """

    def __init__(self, mensaje, codigo="ERROR_DOMINIO", estado=400, params=None):
        self.plantilla = mensaje
        self.params = params or {}
        self.mensaje = mensaje % self.params if self.params else mensaje
        super().__init__(self.mensaje)
        self.codigo = codigo
        self.estado = estado


def respuesta_error(mensaje, codigo, estado):
    return jsonify({"error": mensaje, "codigo": codigo}), estado


def registrar_manejadores(app):
    @app.errorhandler(ErrorDominio)
    def error_dominio(exc):
        return respuesta_error(traducir(exc.plantilla, exc.params), exc.codigo, exc.estado)

    @app.errorhandler(DominioError)
    def regla_de_negocio(exc):
        # Mismo mensaje que v1, en el idioma de la petición; cada clase trae
        # su estado y su código.
        return respuesta_error(traducir(exc.plantilla, exc.params), exc.codigo, exc.estado)

    @app.errorhandler(400)
    def solicitud_incorrecta(exc):
        return respuesta_error(traducir(N_("Solicitud incorrecta")), "ENTRADA_INVALIDA", 400)

    @app.errorhandler(404)
    def no_encontrado(exc):
        return respuesta_error(traducir(N_("Recurso no encontrado")), "NO_ENCONTRADO", 404)

    @app.errorhandler(405)
    def metodo_no_permitido(exc):
        return respuesta_error(traducir(N_("Método no permitido")), "METODO_NO_PERMITIDO", 405)

    @app.errorhandler(500)
    def error_interno(exc):
        return respuesta_error(traducir(N_("Error interno")), "ERROR_INTERNO", 500)

    @app.errorhandler(Exception)
    def inesperado(exc):
        # Otros errores HTTP (p. ej. 413) conservan su estado, pero en JSON.
        if isinstance(exc, HTTPException):
            codigo = _CODIGOS_HTTP.get(exc.code, "ERROR_HTTP")
            return respuesta_error(exc.name, codigo, exc.code)
        # El detalle va al log del servidor, nunca al cliente.
        app.logger.exception("Error inesperado")
        return respuesta_error(traducir(N_("Error interno")), "ERROR_INTERNO", 500)
