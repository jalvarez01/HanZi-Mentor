"""Errores de negocio. errores.py los convierte en JSON con su estado HTTP.

`mensaje` va en español, marcado con N_, y `params` completa sus marcadores
(`%(dias)s`); se traduce al responder, según Accept-Language.
"""


class ErrorSuscripcion(Exception):
    estado = 400

    def __init__(self, mensaje, codigo, **params):
        self.plantilla = mensaje
        self.params = params
        self.codigo = codigo
        super().__init__(mensaje % params if params else mensaje)


class AccionNoPermitida(ErrorSuscripcion):
    """La acción no se puede hacer desde el estado actual de la suscripción."""

    estado = 409


class PagoRechazado(ErrorSuscripcion):
    """La pasarela respondió y no aprobó el cobro."""

    estado = 402


class PasarelaNoDisponible(ErrorSuscripcion):
    """La pasarela no respondió: no se sabe si cobró, así que no se guarda nada."""

    estado = 503
