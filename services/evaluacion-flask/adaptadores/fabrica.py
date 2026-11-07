"""Fábrica de explicadores: el único lugar que conoce los adaptadores concretos.

La configuración (variable EXPLICADOR_ERRORES) elige el adaptador; el resto
del servicio solo recibe un ExplicadorErrores.
"""

from adaptadores.reglas import ExplicadorReglas

_EXPLICADORES = {
    "reglas": lambda config: ExplicadorReglas(),
}


def crear_explicador(config):
    nombre = config["EXPLICADOR_ERRORES"]
    try:
        constructor = _EXPLICADORES[nombre]
    except KeyError:
        # Falla al arrancar, no en la primera petición: una configuración
        # equivocada se detecta en el deploy.
        validos = ", ".join(sorted(_EXPLICADORES))
        raise ValueError(f"EXPLICADOR_ERRORES='{nombre}' no existe. Opciones: {validos}") from None
    return constructor(config)
