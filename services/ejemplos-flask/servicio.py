"""Caso de uso: buscar oraciones de ejemplo para un carácter.

Solo conoce el puerto ProveedorEjemplos, nunca un adaptador concreto.
"""

from dominio.puertos import ProveedorNoDisponible
from errores import ErrorDominio


def buscar_ejemplos(proveedor, hanzi, idioma, limite):
    try:
        ejemplos = proveedor.obtener(hanzi, idioma, limite)
    except ProveedorNoDisponible:
        raise ErrorDominio(
            "El proveedor de ejemplos no está disponible",
            "PROVEEDOR_NO_DISPONIBLE",
            estado=503,
        ) from None

    return {
        "hanzi": hanzi,
        "idioma": idioma,
        "proveedor": proveedor.nombre,
        "ejemplos": [ejemplo.a_dict() for ejemplo in ejemplos[:limite]],
    }
