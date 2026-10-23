"""Puerto (interfaz) hacia los proveedores de oraciones de ejemplo.

Patrón Adapter con Inversión de Dependencias: el caso de uso depende de esta
interfaz, no de una API concreta. Cada proveedor externo se conecta con su
propio adaptador en `adaptadores/`, y la fábrica decide cuál usar según la
configuración. Cambiar de proveedor no toca el dominio ni el caso de uso.
"""

from abc import ABC, abstractmethod


class ProveedorNoDisponible(Exception):
    """El proveedor externo no respondió, tardó demasiado o respondió algo inválido."""


class ProveedorEjemplos(ABC):
    """Fuente de oraciones de ejemplo para un carácter o palabra en chino."""

    #: Nombre corto del proveedor, se devuelve en la respuesta de la API.
    nombre = "desconocido"
    #: Crédito que exige la licencia de los datos, o None si no aplica.
    atribucion = None

    @abstractmethod
    def obtener(self, hanzi, idioma, limite):
        """Devuelve hasta `limite` objetos `Ejemplo` que contienen `hanzi`.

        `idioma` es el idioma de la traducción ("es" o "en"). Si el proveedor
        no tiene ejemplos devuelve una lista vacía; si no se puede consultar,
        lanza `ProveedorNoDisponible`.
        """
