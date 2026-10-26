"""Errores de reglas de negocio.

Cada clase trae el estado HTTP y el código con que la responde errores.py.
"""


class DominioError(Exception):
    """Error de reglas de negocio. La capa HTTP lo traduce a 400."""

    estado = 400
    codigo = "ERROR_DOMINIO"


class CaracterNoEncontradoError(DominioError):
    """El catálogo no tiene el carácter pedido."""

    estado = 404
    codigo = "NO_ENCONTRADO"


class TrazoNoEncontradoError(DominioError):
    """El carácter no tiene un trazo con esa secuencia."""

    estado = 404
    codigo = "NO_ENCONTRADO"


class DependenciaNoDisponibleError(DominioError):
    """Catálogo o trazos no respondieron: no se adivina un resultado."""

    estado = 503
    codigo = "DEPENDENCIA_NO_DISPONIBLE"
