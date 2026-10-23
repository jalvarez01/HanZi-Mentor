"""Fábrica de proveedores: el único lugar que conoce los adaptadores concretos.

La configuración (variable PROVEEDOR_EJEMPLOS) elige el adaptador; el resto
del servicio solo recibe un ProveedorEjemplos.
"""

from adaptadores.falso import EjemplosFalsos
from adaptadores.tatoeba import AdaptadorTatoeba

_PROVEEDORES = {
    "tatoeba": lambda config: AdaptadorTatoeba(config["TATOEBA_URL"], config["TATOEBA_TIMEOUT"]),
    "falso": lambda config: EjemplosFalsos(),
}


def crear_proveedor(config):
    nombre = config["PROVEEDOR_EJEMPLOS"]
    try:
        constructor = _PROVEEDORES[nombre]
    except KeyError:
        # Falla al arrancar, no en la primera petición: una configuración
        # equivocada se detecta en el deploy.
        validos = ", ".join(sorted(_PROVEEDORES))
        raise ValueError(f"PROVEEDOR_EJEMPLOS='{nombre}' no existe. Opciones: {validos}") from None
    return constructor(config)
