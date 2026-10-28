"""Valida la forma de la entrada antes de llegar al servicio.

Cada error se lanza como ErrorDominio con 400 y código ENTRADA_INVALIDA.
"""

import re
import uuid

from errores import ErrorDominio
from mensajes import N_

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _invalida(mensaje):
    return ErrorDominio(mensaje, "ENTRADA_INVALIDA")


def _es_uuid(texto):
    return isinstance(texto, str) and bool(_UUID.match(texto))


def validar_usuario_id(texto):
    """UUID con guiones, igual que progreso-flask. Devuelve el texto normalizado."""
    if not _es_uuid(texto):
        raise _invalida(N_("El usuario_id debe ser un UUID válido"))
    return str(uuid.UUID(texto))


def validar_pedido_reporte(datos):
    """Cuerpo de POST /api/v2/reportes/: {"usuario_id": "<uuid>"}."""
    if not isinstance(datos, dict):
        raise _invalida(N_("El cuerpo debe ser un objeto JSON"))
    return validar_usuario_id(datos.get("usuario_id"))


def validar_task_id(texto):
    """Celery crea los task_id como UUID."""
    if not _es_uuid(texto):
        raise _invalida(N_("El task_id debe ser un UUID válido"))
    return texto.lower()
