"""Elige el adaptador según ALIADO_PROVEEDOR (inversión de dependencias)."""

from adaptadores.falso import CajasFalsas
from adaptadores.vaultdrop import AdaptadorVaultDrop


def crear_proveedor(config):
    nombre = config["ALIADO_PROVEEDOR"]
    if nombre == "vaultdrop":
        return AdaptadorVaultDrop(config["ALIADO_URL"], config["ALIADO_TIMEOUT"])
    if nombre == "falso":
        return CajasFalsas()
    raise ValueError(f"ALIADO_PROVEEDOR desconocido: {nombre!r}. Opciones: falso, vaultdrop")
