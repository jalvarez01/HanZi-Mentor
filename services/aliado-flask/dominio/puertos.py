"""Puerto (interfaz) hacia el servicio del equipo aliado.

Patrón Adapter con Inversión de Dependencias, igual que ejemplos-flask con
Tatoeba: el caso de uso depende de esta interfaz y la fábrica decide qué
adaptador usar según ALIADO_PROVEEDOR. Si VaultDrop cambia su API, o se
cambia de aliado, solo cambia el adaptador.
"""

from abc import ABC, abstractmethod


class AliadoNoDisponible(Exception):
    """El aliado no respondió, tardó demasiado o respondió algo inválido."""


class ProveedorCajas(ABC):
    #: Nombre corto del proveedor, se devuelve en la respuesta.
    nombre = "desconocido"
    #: Nombre del sistema del aliado, para mostrarlo en la app.
    sistema = "VaultDrop"

    @abstractmethod
    def obtener_cajas(self):
        """Lista de `Caja` activas del aliado. Lanza AliadoNoDisponible."""
