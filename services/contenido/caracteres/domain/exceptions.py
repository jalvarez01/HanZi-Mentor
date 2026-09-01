class DominioError(Exception):
    """Error de reglas de negocio. La capa de interfaz lo traduce a HTTP."""


class CaracterNoEncontradoError(DominioError):
    """No existe un carácter con el hanzi solicitado."""


class TrazoNoEncontradoError(DominioError):
    """El carácter existe pero no tiene un trazo con esa secuencia."""
