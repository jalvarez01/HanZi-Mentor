"""Errores de reglas de negocio. Port de agente-tutor/tutor/domain/exceptions.py.

Cada clase trae el estado HTTP y el código con que la responde errores.py.
"""


class DominioError(Exception):
    """Error de reglas de negocio. La capa HTTP lo traduce a 400.

    El mensaje va en español, marcado con N_, y `params` completa sus
    marcadores (`%(nivel)s`). errores.py lo traduce al idioma de la petición;
    str(error) da el texto en español, como antes.
    """

    estado = 400
    codigo = "ERROR_DOMINIO"

    def __init__(self, mensaje="", **params):
        self.plantilla = mensaje
        self.params = params
        super().__init__(mensaje % params if params else mensaje)


class SesionInvalidaError(DominioError):
    """La sesión no cumple las invariantes mínimas para persistirse."""

    codigo = "SESION_INVALIDA"


class NivelNoPermitidoError(DominioError):
    """El usuario intenta practicar un nivel HSK que aún no desbloqueó."""

    codigo = "NIVEL_NO_PERMITIDO"


class EjercicioYaRespondidoError(DominioError):
    """No se puede responder dos veces el mismo ejercicio."""

    estado = 409
    codigo = "EJERCICIO_YA_RESPONDIDO"


class EjercicioNoEncontradoError(DominioError):
    """No existe un ejercicio con el id solicitado."""

    estado = 404
    codigo = "NO_ENCONTRADO"


class SesionNoEncontradaError(DominioError):
    """No existe una sesión con el id solicitado."""

    estado = 404
    codigo = "NO_ENCONTRADO"
