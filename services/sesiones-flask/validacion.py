"""Valida la forma de la entrada, como los serializers de entrada de v1.

Cada error se lanza como ErrorDominio con 400 y código ENTRADA_INVALIDA.
"""

import uuid

from dominio.codigos_error import CODIGOS_ERROR
from errores import ErrorDominio
from mensajes import N_

DURACION_DEFECTO = 10

# Los mismos valores que acepta BooleanField de DRF.
VERDADEROS = {"t", "T", "y", "Y", "yes", "Yes", "YES", "true", "True", "TRUE", "on", "On", "ON", "1", 1, True}
FALSOS = {"f", "F", "n", "N", "no", "No", "NO", "false", "False", "FALSE", "off", "Off", "OFF", "0", 0, 0.0, False}


def _invalida(mensaje, **params):
    return ErrorDominio(mensaje, "ENTRADA_INVALIDA", params=params)


def _cuerpo(datos):
    if not isinstance(datos, dict):
        raise _invalida(N_("El cuerpo debe ser un objeto JSON"))
    return datos


def _uuid(valor):
    """Como UUIDField de DRF: el texto del UUID o un entero."""
    if isinstance(valor, bool):
        return None
    try:
        if isinstance(valor, int):
            return uuid.UUID(int=valor)
        if isinstance(valor, str):
            return uuid.UUID(valor)
    except ValueError:
        return None
    return None


def _entero(valor):
    """Como IntegerField de DRF: acepta 3, 3.0 y "3"; no True ni 3.5."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.lstrip("-").isdigit():
            return int(texto)
    return None


def _entero_en_rango(datos, campo, minimo, maximo, defecto=None):
    if campo not in datos:
        if defecto is None:
            raise _invalida(N_("El campo '%(campo)s' es obligatorio"), campo=campo)
        return defecto
    valor = _entero(datos[campo])
    if valor is None or not minimo <= valor <= maximo:
        raise _invalida(
            N_("El campo '%(campo)s' debe ser un entero entre %(minimo)s y %(maximo)s"),
            campo=campo, minimo=minimo, maximo=maximo,
        )
    return valor


def validar_crear_sesion(datos):
    """Devuelve (usuario_id, nivel_hsk, duracion_min) de POST /api/v2/sesiones/."""
    datos = _cuerpo(datos)
    if "usuario_id" not in datos:
        raise _invalida(N_("El campo '%(campo)s' es obligatorio"), campo="usuario_id")
    usuario_id = _uuid(datos["usuario_id"])
    if usuario_id is None:
        raise _invalida(N_("El campo '%(campo)s' debe ser un UUID válido"), campo="usuario_id")

    nivel_hsk = _entero_en_rango(datos, "nivel_hsk", 1, 6)
    duracion = _entero_en_rango(datos, "duracion_min", 5, 60, defecto=DURACION_DEFECTO)
    return usuario_id, nivel_hsk, duracion


LIMITE_HISTORIAL = 10


def validar_historial(args):
    """Devuelve (usuario_id, limite) de GET /api/v2/sesiones/desempeno/."""
    if not args.get("usuario_id"):
        raise _invalida(N_("El campo '%(campo)s' es obligatorio"), campo="usuario_id")
    usuario_id = _uuid(args.get("usuario_id"))
    if usuario_id is None:
        raise _invalida(N_("El campo '%(campo)s' debe ser un UUID válido"), campo="usuario_id")
    limite = _entero_en_rango(args, "limite", 1, 50, defecto=LIMITE_HISTORIAL)
    return usuario_id, limite


def _acerto(datos):
    if "acerto" not in datos:
        raise _invalida(N_("El campo '%(campo)s' es obligatorio"), campo="acerto")
    valor = datos["acerto"]
    try:
        if valor in VERDADEROS:
            return True
        if valor in FALSOS:
            return False
    except TypeError:
        # Listas o dicts no se pueden buscar en un set.
        pass
    raise _invalida(N_("El campo 'acerto' debe ser true o false"))


def validar_respuesta(datos):
    """Devuelve (acerto, codigo_error) de POST /api/v2/ejercicios/<id>/responder/.

    `codigo_error` es opcional (RF-IA-01): el tipo de error de una respuesta
    fallada. Con un acierto se ignora sin revisarlo, para que un cliente que
    lo manda de más no pierda la respuesta.
    """
    datos = _cuerpo(datos)
    acerto = _acerto(datos)

    codigo_error = None if acerto else datos.get("codigo_error")
    if codigo_error is not None and (
        not isinstance(codigo_error, str) or codigo_error not in CODIGOS_ERROR
    ):
        raise _invalida(N_("El campo 'codigo_error' no es un código de error conocido"))
    return acerto, codigo_error
