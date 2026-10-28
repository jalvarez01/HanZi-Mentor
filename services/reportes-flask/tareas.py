"""Aplicación Celery y tareas del worker (T18 y T19).

El worker arranca con `celery -A tareas worker` y la app Flask encola con
este mismo `celery_app`. Este módulo no importa Flask: el worker no lo
necesita.

Cada tarea tiene un nombre explícito para que otros servicios la publiquen
con `send_task("<nombre>")` sin importar este código.
"""

import uuid
from datetime import datetime, timezone

from celery import Celery
from celery.utils.log import get_task_logger

import config
from clientes import ServicioNoDisponible
from dominio.excepciones import CODIGO_GENERICO, MENSAJE_GENERICO, DependenciaNoDisponible, ErrorReporte
from dominio.reporte import armar_reporte, fecha_iso
from fabricas import crear_dependencias, crear_redis

CONFIG = config.desde_entorno()

# Progreso caído: 4 intentos (1 + 3 reintentos) separados por 1, 2 y 4 s.
# Con HTTP_TIMEOUT=3, en el peor caso 4 x 3 s + 7 s = 19 s hasta "error".
# Con el contenedor de progreso detenido, cada intento tarda unos 4 s (la
# resolución DNS no respeta el timeout): 4 x 4 s + 7 s = 23 s.
MAX_REINTENTOS = 3
BACKOFF_SEGUNDOS = 1

logger = get_task_logger(__name__)

celery_app = Celery("reportes", broker=CONFIG["REDIS_URL"], backend=CONFIG["REDIS_URL"])
celery_app.conf.update(
    # Solo JSON: el worker nunca deserializa pickle que llegue por la cola.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Los resultados caducan a las 24 h. Con caducidad, Redis puede
    # expulsarlos (volatile-lru); la cola no caduca y nunca se expulsa.
    result_expires=86400,
    # Distingue "en_proceso" de "pendiente" en GET /api/v2/reportes/<id>/.
    task_track_started=True,
    task_soft_time_limit=30,
    # Con --concurrency=1, el worker toma una tarea por vez.
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    # Si Redis no responde, leer un resultado falla en 1 s y no se queda colgado.
    redis_socket_connect_timeout=1,
    redis_socket_timeout=3,
)

# Se crean en la primera tarea, no al importar: así las pruebas pueden
# reemplazarlas con `tareas.dependencias = ...` sin tocar la red.
dependencias = None


def obtener_dependencias():
    global dependencias
    if dependencias is None:
        dependencias = crear_dependencias(CONFIG, crear_redis(CONFIG))
    return dependencias


@celery_app.task(name="ping")
def ping():
    """Prueba del viaje completo: encolar -> worker -> resultado."""
    return "pong"


@celery_app.task(
    name="generar_reporte_progreso",
    bind=True,
    autoretry_for=(DependenciaNoDisponible,),
    max_retries=MAX_REINTENTOS,
    # Espera = 1 * 2^reintento: 1, 2 y 4 s, sin azar.
    retry_backoff=BACKOFF_SEGUNDOS,
    retry_backoff_max=BACKOFF_SEGUNDOS * 2 ** (MAX_REINTENTOS - 1),
    retry_jitter=False,
)
def generar_reporte_progreso(self, usuario_id):
    """Resumen del progreso de un usuario. Termina en error con un código
    (ErrorReporte) si progreso no responde después de los reintentos."""
    try:
        progreso = obtener_dependencias().progreso.obtener(usuario_id)
    except ServicioNoDisponible as error:
        es_4xx = error.estado is not None and 400 <= error.estado < 500
        if es_4xx:
            # Reintentar no lo arregla: la ruta ya validó el UUID.
            logger.error("Progreso rechazó el reporte de %s: %s", usuario_id, error)
            raise ErrorReporte(CODIGO_GENERICO, MENSAJE_GENERICO) from None
        logger.warning(
            "Progreso no disponible para %s (intento %s de %s): %s",
            usuario_id, self.request.retries + 1, MAX_REINTENTOS + 1, error,
        )
        raise DependenciaNoDisponible() from None
    return armar_reporte(progreso, datetime.now(timezone.utc))


@celery_app.task(name="notificar_sesion_lista", ignore_result=True)
def notificar_sesion_lista(usuario_id, sesion_id):
    """La publica sesiones-flask por nombre al crear una sesión."""
    try:
        usuario_id = str(uuid.UUID(str(usuario_id)))
    except ValueError:
        # No se arma una clave de Redis con un id inválido.
        logger.warning("Notificación descartada: usuario_id inválido %r", usuario_id)
        return
    notificacion = {
        "tipo": "sesion_lista",
        "sesion_id": sesion_id,
        "creada_en": fecha_iso(datetime.now(timezone.utc)),
    }
    obtener_dependencias().notificaciones.agregar(usuario_id, notificacion)
    logger.info("Sesión %s lista para %s", sesion_id, usuario_id)
