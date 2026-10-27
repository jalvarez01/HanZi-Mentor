"""Aplicación Celery y tareas del worker (T18 y T19).

El worker arranca con `celery -A tareas worker` y la app Flask encola con
este mismo `celery_app`. Este módulo no importa Flask: el worker no lo
necesita.

Cada tarea tiene un nombre explícito para que otros servicios la publiquen
con `send_task("<nombre>")` sin importar este código.
"""

from celery import Celery

import config

CONFIG = config.desde_entorno()

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
)


@celery_app.task(name="ping")
def ping():
    """Prueba del viaje completo: encolar -> worker -> resultado."""
    return "pong"
