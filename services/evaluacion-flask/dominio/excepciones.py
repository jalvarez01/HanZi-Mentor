"""Errores de reglas de negocio.

Cada clase trae el estado HTTP y el código con que la responde errores.py.
"""


class DominioError(Exception):
    """Error de reglas de negocio. La capa HTTP lo traduce a 400.

    El mensaje va en español, marcado con N_, y `params` completa sus
    marcadores (`%(hanzi)s`). errores.py lo traduce al idioma de la petición;
    str(error) da el texto en español.
    """

    estado = 400
    codigo = "ERROR_DOMINIO"

    def __init__(self, mensaje="", **params):
        self.plantilla = mensaje
        self.params = params
        super().__init__(mensaje % params if params else mensaje)


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
