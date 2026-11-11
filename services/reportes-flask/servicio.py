"""Casos de uso: encolar reportes, leer su estado y leer notificaciones.

Estados de Celery -> estados de la API:

    PENDING, RECEIVED -> pendiente
    STARTED, RETRY    -> en_proceso
    SUCCESS           -> listo
    FAILURE, REVOKED  -> error

Celery no guarda una lista de las tareas encoladas: un task_id que nunca
existió, o cuyo resultado ya caducó, también se lee como PENDING. Para
distinguirlo, al encolar se guarda la marca `reporte:<task_id>` con la
misma caducidad que los resultados (24 h). Se responde 404 solo si no hay
marca Y Celery dice PENDING: si Celery tiene un estado (STARTED, RETRY,
SUCCESS, FAILURE) se devuelve aunque la marca no exista, porque Redis puede
haberla expulsado antes (volatile-lru).
"""

import logging
import uuid

import redis
from kombu.exceptions import OperationalError

from dominio.excepciones import CODIGO_GENERICO, MENSAJE_GENERICO, ErrorReporte
from errores import ErrorDominio
from mensajes import N_
from tareas import RESULTADOS_CADUCAN_EN, celery_app

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


def clave_reporte(task_id):
    return f"reporte:{task_id}"


def no_encontrado():
    return ErrorDominio(N_("No existe un reporte con ese task_id."), "NO_ENCONTRADO", 404)


def encolar_reporte(publicador, redis_cliente, usuario_id):
    """Guarda la marca del reporte, lo encola y devuelve su task_id.

    Si falla cualquiera de los dos pasos, 503. Si la marca se guardó pero la
    publicación falló, se intenta borrarla para que el id no quede como
    "pendiente" durante 24 h.
    """
    task_id = str(uuid.uuid4())
    clave = clave_reporte(task_id)
    marca_guardada = False
    try:
        redis_cliente.set(clave, "1", ex=RESULTADOS_CADUCAN_EN)
        marca_guardada = True
        publicador.send_task("generar_reporte_progreso", args=[usuario_id], task_id=task_id)
    except ERRORES_DE_COLA as error:
        logger.warning("No se pudo encolar el reporte de %s: %s", usuario_id, error)
        # Solo si la marca llegó a guardarse: con Redis caído, borrar otra vez
        # sumaría el tiempo de un segundo intento de conexión.
        if marca_guardada:
            try:
                redis_cliente.delete(clave)
            except ERRORES_DE_COLA:
                pass
        raise cola_no_disponible() from None
    return task_id


def _codigo_y_mensaje(excepcion):
    """El código y el mensaje (en español) de una tarea que falló."""
    if isinstance(excepcion, ErrorReporte):
        return excepcion.codigo, excepcion.mensaje
    return CODIGO_GENERICO, MENSAJE_GENERICO


def consultar_reporte(redis_cliente, task_id):
    """Dict con task_id y estado, más `resultado` (listo) o `error` y `codigo`.

    404 si no hay marca y Celery no tiene estado. `error` queda en español;
    la ruta lo traduce.
    """
    try:
        resultado = celery_app.AsyncResult(task_id)
        estado_celery = resultado.state
        valor = resultado.result
        # La marca solo decide cuando Celery no sabe nada de la tarea.
        existe = estado_celery != "PENDING" or redis_cliente.exists(clave_reporte(task_id))
    except ERRORES_DE_COLA as error:
        logger.warning("No se pudo leer el reporte %s: %s", task_id, error)
        raise cola_no_disponible() from None

    if not existe:
        raise no_encontrado()

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
