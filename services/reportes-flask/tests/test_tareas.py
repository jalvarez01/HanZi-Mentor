"""Configuración de Celery y tarea ping, sin Redis ni worker."""

import config
from tareas import celery_app, ping


def test_ajustes_de_celery():
    conf = celery_app.conf

    assert conf.result_expires == 86400
    assert conf.task_track_started is True
    assert conf.task_soft_time_limit == 30
    assert conf.worker_prefetch_multiplier == 1


def test_solo_json_en_la_cola_y_en_los_resultados():
    conf = celery_app.conf

    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert list(conf.accept_content) == ["json"]


def test_broker_y_backend_desde_redis_url():
    url = config.desde_entorno()["REDIS_URL"]

    assert celery_app.conf.broker_url == url
    assert celery_app.conf.result_backend == url


def test_ping_registrada_por_nombre():
    assert "ping" in celery_app.tasks


def test_ping_responde_pong():
    assert ping() == "pong"
    # Modo eager: corre en el proceso, sin broker.
    assert ping.apply().get() == "pong"
