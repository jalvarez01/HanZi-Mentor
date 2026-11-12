"""Adaptador falso: dos cajas fijas, sin red, con las rarezas de VaultDrop
(COMUN, RARO, EPICO y LEGENDARIO).

Para las pruebas y para correr la app en local sin la IP del aliado. La
respuesta lleva `proveedor: "falso"` y el frontend avisa que son datos de
ejemplo.
"""

from decimal import Decimal

from dominio.caja import Caja, Item
from dominio.puertos import ProveedorCajas


def _item(nombre, rareza, valor, probabilidad):
    return Item(nombre, rareza, valor, "", Decimal(probabilidad))


CAJAS = (
    Caja(
        id=1,
        nombre="Caja de prueba",
        precio="10.00",
        imagen_url="",
        items=(
            _item("AK-47 | Redline", "EPICO", "85.00", "15"),
            _item("Glock-18 | Water Elemental", "RARO", "12.00", "35"),
            _item("P250 | Sand Dune", "COMUN", "0.50", "50"),
        ),
    ),
    Caja(
        id=2,
        nombre="Caja legendaria de prueba",
        precio="50.00",
        imagen_url="",
        items=(
            _item("AWP | Dragon Lore", "LEGENDARIO", "850.00", "1"),
            _item("M4A4 | Howl", "LEGENDARIO", "320.00", "9"),
            _item("USP-S | Orion", "EPICO", "40.00", "90"),
        ),
    ),
)


class CajasFalsas(ProveedorCajas):
    nombre = "falso"

    def __init__(self, cajas=CAJAS):
        self._cajas = list(cajas)

    def obtener_cajas(self):
        return list(self._cajas)
