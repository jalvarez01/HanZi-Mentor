"""Errores de reglas de negocio. Port de agente-tutor/tutor/domain/exceptions.py.

Cada clase trae el estado HTTP y el código con que la responde errores.py.
"""


class DominioError(Exception):
    """Error de reglas de negocio. La capa HTTP lo traduce a 400."""

    estado = 400
    codigo = "ERROR_DOMINIO"


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
