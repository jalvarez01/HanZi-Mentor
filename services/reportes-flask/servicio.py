"""Casos de uso: encolar reportes, leer su estado y leer notificaciones.

Estados de Celery -> estados de la API:

    PENDING, RECEIVED -> pendiente
    STARTED, RETRY    -> en_proceso
    SUCCESS           -> listo
    FAILURE, REVOKED  -> error

Limitación de Celery: un task_id que nunca existió (o cuyo resultado ya
caducó a las 24 h) también se lee como PENDING, así que la API responde
"pendiente". Celery no guarda una lista de las tareas encoladas.
"""

import logging

import redis
from kombu.exceptions import OperationalError

from dominio.excepciones import CODIGO_GENERICO, MENSAJE_GENERICO, ErrorReporte
from errores import ErrorDominio
from mensajes import N_
from tareas import celery_app

logger = logging.getLogger(__name__)

ESTADOS = {
    "PENDING": "pendiente",
    "RECEIVED": "pendiente",
    "STARTED": "en_proceso",
    "RETRY": "en_proceso",
    "SUCCESS": "listo",
    "FAILURE": "error",
    "REVOKED": "error",
}

# Lo que lanzan kombu (broker) y redis-py (resultados) si Redis no responde.
ERRORES_DE_COLA = (OperationalError, redis.RedisError, OSError)


def cola_no_disponible():
    return ErrorDominio(N_("La cola de tareas no está disponible."), "COLA_NO_DISPONIBLE", 503)


def encolar_reporte(publicador, usuario_id):
    """Devuelve el task_id. Si Redis no responde, falla en 1 o 2 s (ver
    fabricas.crear_publicador)."""
    try:
        resultado = publicador.send_task("generar_reporte_progreso", args=[usuario_id])
    except ERRORES_DE_COLA as error:
        logger.warning("No se pudo encolar el reporte de %s: %s", usuario_id, error)
        raise cola_no_disponible() from None
    return resultado.id


def _codigo_y_mensaje(excepcion):
    """El código y el mensaje (en español) de una tarea que falló."""
    if isinstance(excepcion, ErrorReporte):
        return excepcion.codigo, excepcion.mensaje
    return CODIGO_GENERICO, MENSAJE_GENERICO


def consultar_reporte(task_id):
    """Dict con task_id y estado, más `resultado` (listo) o `error` y `codigo`.

    `error` queda en español; la ruta lo traduce.
    """
    try:
        resultado = celery_app.AsyncResult(task_id)
        estado_celery = resultado.state
        valor = resultado.result
    except ERRORES_DE_COLA as error:
        logger.warning("No se pudo leer el reporte %s: %s", task_id, error)
        raise cola_no_disponible() from None

    estado = ESTADOS.get(estado_celery, "pendiente")
    respuesta = {"task_id": task_id, "estado": estado}
    if estado == "listo":
        respuesta["resultado"] = valor
    elif estado == "error":
        respuesta["codigo"], respuesta["error"] = _codigo_y_mensaje(valor)
    return respuesta


def listar_notificaciones(notificaciones, usuario_id):
    try:
        return notificaciones.listar(usuario_id)
    except ERRORES_DE_COLA as error:
        logger.warning("No se pudieron leer las notificaciones de %s: %s", usuario_id, error)
        raise cola_no_disponible() from None
