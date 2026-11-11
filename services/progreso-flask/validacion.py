"""Valida la forma de la entrada antes de llegar al servicio.

Cada error se lanza como ErrorDominio con 400 y código ENTRADA_INVALIDA.
"""

import re
import uuid

from dominio.codigos import CODIGOS_ERROR, CODIGOS_TRAZO_EVALUADO
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


def _caracter(datos):
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
    return caracter


def _codigo_error(datos, permitidos):
    """El `codigo_error` del cuerpo, o None si no viene."""
    codigo = datos.get("codigo_error")
    if codigo is None:
        return None
    if not isinstance(codigo, str) or codigo not in permitidos:
        raise _invalida(N_("El campo 'codigo_error' no es un código de error conocido"))
    return codigo


def validar_respuesta(datos):
    """Devuelve (caracter, acerto, codigo_error) del cuerpo de POST .../respuestas/.

    `codigo_error` es opcional (RF-IA-01) y solo vale para un fallo: con
    `acerto` true se ignora sin revisarlo, para que un cliente que lo manda
    de más no pierda la respuesta.
    """
    caracter = _caracter(datos)

    acerto = datos.get("acerto")
    if not isinstance(acerto, bool):
        raise _invalida(N_("El campo 'acerto' es obligatorio y debe ser true o false"))

    codigo_error = None if acerto else _codigo_error(datos, CODIGOS_ERROR)
    return caracter, acerto, codigo_error


def validar_error_de_trazo(datos):
    """Devuelve (caracter, codigo_error) del cuerpo de POST .../errores/.

    Solo acepta los códigos de un trazo evaluado por evaluacion-flask.
    """
    caracter = _caracter(datos)
    codigo_error = _codigo_error(datos, CODIGOS_ERROR)
    if codigo_error is None:
        raise _invalida(N_("El campo 'codigo_error' es obligatorio"))
    if codigo_error not in CODIGOS_TRAZO_EVALUADO:
        raise _invalida(N_("El campo 'codigo_error' debe ser un código de error de trazo"))
    return caracter, codigo_error


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
