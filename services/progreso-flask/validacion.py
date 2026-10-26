"""Valida la forma de la entrada antes de llegar al servicio.

Cada error se lanza como ErrorDominio con 400 y código ENTRADA_INVALIDA.
"""

import re
import uuid

from errores import ErrorDominio
from mensajes import N_

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Igual que Ejercicio.caracter (max_length=8) en agente-tutor.
MAX_CARACTER = 8

LIMITE_DEFECTO = 3
LIMITE_MAXIMO = 50


def _invalida(mensaje, **params):
    return ErrorDominio(mensaje, "ENTRADA_INVALIDA", params=params)


def validar_usuario_id(texto):
    """UUID con guiones, como el convertidor <uuid:> de Django en v1."""
    if not _UUID.match(texto):
        raise _invalida(N_("El usuario_id debe ser un UUID válido"))
    return uuid.UUID(texto)


def validar_respuesta(datos):
    """Devuelve (caracter, acerto) del cuerpo de POST .../respuestas/."""
    if not isinstance(datos, dict):
        raise _invalida(N_("El cuerpo debe ser un objeto JSON"))

    caracter = datos.get("caracter")
    if not isinstance(caracter, str) or not caracter.strip():
        raise _invalida(N_("El campo 'caracter' es obligatorio y debe ser texto"))
    caracter = caracter.strip()
    if len(caracter) > MAX_CARACTER:
        raise _invalida(
            N_("El campo 'caracter' admite hasta %(maximo)s caracteres"), maximo=MAX_CARACTER
        )

    acerto = datos.get("acerto")
    if not isinstance(acerto, bool):
        raise _invalida(N_("El campo 'acerto' es obligatorio y debe ser true o false"))

    return caracter, acerto


def validar_limite(argumentos):
    texto = argumentos.get("limite")
    if texto is None:
        return LIMITE_DEFECTO
    texto = texto.strip()
    if not texto.isdigit() or not 1 <= int(texto) <= LIMITE_MAXIMO:
        raise _invalida(
            N_("El límite debe ser un entero entre 1 y %(maximo)s"), maximo=LIMITE_MAXIMO
        )
    return int(texto)
