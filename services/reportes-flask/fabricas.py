"""Arma las dependencias según la configuración. No importa Flask: la usan
la app Flask y el worker de Celery."""

from dataclasses import dataclass

import redis
from celery import Celery

from clientes import ClienteHttp, ProgresoRemoto
from notificaciones import NotificacionesRedis


@dataclass
class Dependencias:
    progreso: ProgresoRemoto
    notificaciones: NotificacionesRedis


def crear_redis(config):
    """Cliente perezoso: no conecta hasta la primera orden."""
    return redis.Redis.from_url(
        config["REDIS_URL"],
        socket_connect_timeout=config["REDIS_TIMEOUT"],
        socket_timeout=config["REDIS_TIMEOUT"],
    )


def crear_publicador(config):
    """App Celery solo para encolar desde Flask, por nombre de tarea.

    No tiene backend de resultados a propósito: con el de Redis, cada
    publicación abre una suscripción pub/sub al resultado que la app Flask
    nunca espera (crece con cada reporte) y, con Redis caído, reintenta
    unos 40 s antes de fallar. Los resultados se leen con
    `tareas.celery_app.AsyncResult`, que es un GET simple.

    Sin reintentos y con timeouts de REDIS_TIMEOUT: si Redis no responde,
    la publicación falla en 1 o 2 s y la ruta responde 503.
    """
    # set_as_current=False: la app "actual" del proceso sigue siendo tareas.celery_app.
    publicador = Celery("reportes-publicador", broker=config["REDIS_URL"], set_as_current=False)
    publicador.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_publish_retry=False,
        broker_connection_timeout=config["REDIS_TIMEOUT"],
        broker_connection_retry_on_startup=False,
        broker_transport_options={
            "socket_connect_timeout": config["REDIS_TIMEOUT"],
            "socket_timeout": config["REDIS_TIMEOUT"],
        },
    )
    return publicador


def crear_dependencias(config, redis_cliente):
    # reintentos=0: los reintentos los hace Celery (ver tareas.py). Con dos
    # capas de reintentos, un progreso caído tardaría más de 30 s en dar error.
    cliente = ClienteHttp(config["PROGRESO_URL"], timeout=config["HTTP_TIMEOUT"], reintentos=0)
    return Dependencias(
        progreso=ProgresoRemoto(cliente),
        notificaciones=NotificacionesRedis(redis_cliente),
    )
