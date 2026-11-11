"""Elige la pasarela según PASARELA_PAGO (inversión de dependencias)."""

from pasarelas.simulada import PasarelaSimulada

PASARELAS = {
    "simulada": PasarelaSimulada,
}


def crear_pasarela(nombre):
    try:
        return PASARELAS[nombre]()
    except KeyError:
        opciones = ", ".join(sorted(PASARELAS))
        raise ValueError(f"PASARELA_PAGO desconocida: {nombre!r}. Opciones: {opciones}") from None
