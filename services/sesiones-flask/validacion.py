"""Valida la forma de la entrada, como los serializers de entrada de v1.

Cada error se lanza como ErrorDominio con 400 y código ENTRADA_INVALIDA.
"""

import uuid

from errores import ErrorDominio

DURACION_DEFECTO = 10

# Los mismos valores que acepta BooleanField de DRF.
VERDADEROS = {"t", "T", "y", "Y", "yes", "Yes", "YES", "true", "True", "TRUE", "on", "On", "ON", "1", 1, True}
FALSOS = {"f", "F", "n", "N", "no", "No", "NO", "false", "False", "FALSE", "off", "Off", "OFF", "0", 0, 0.0, False}


def _invalida(mensaje):
    return ErrorDominio(mensaje, "ENTRADA_INVALIDA")


def _cuerpo(datos):
    if not isinstance(datos, dict):
        raise _invalida("El cuerpo debe ser un objeto JSON")
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
            raise _invalida(f"El campo '{campo}' es obligatorio")
        return defecto
    valor = _entero(datos[campo])
    if valor is None or not minimo <= valor <= maximo:
        raise _invalida(f"El campo '{campo}' debe ser un entero entre {minimo} y {maximo}")
    return valor


def validar_crear_sesion(datos):
    """Devuelve (usuario_id, nivel_hsk, duracion_min) de POST /api/v2/sesiones/."""
    datos = _cuerpo(datos)
    if "usuario_id" not in datos:
        raise _invalida("El campo 'usuario_id' es obligatorio")
    usuario_id = _uuid(datos["usuario_id"])
    if usuario_id is None:
        raise _invalida("El campo 'usuario_id' debe ser un UUID válido")

    nivel_hsk = _entero_en_rango(datos, "nivel_hsk", 1, 6)
    duracion = _entero_en_rango(datos, "duracion_min", 5, 60, defecto=DURACION_DEFECTO)
    return usuario_id, nivel_hsk, duracion


def validar_respuesta(datos):
    """Devuelve `acerto` de POST /api/v2/ejercicios/<id>/responder/."""
    datos = _cuerpo(datos)
    if "acerto" not in datos:
        raise _invalida("El campo 'acerto' es obligatorio")
    valor = datos["acerto"]
    try:
        if valor in VERDADEROS:
            return True
        if valor in FALSOS:
            return False
    except TypeError:
        # Listas o dicts no se pueden buscar en un set.
        pass
    raise _invalida("El campo 'acerto' debe ser true o false")
