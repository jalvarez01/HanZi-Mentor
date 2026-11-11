"""Dominio, cliente de progreso, repositorio de notificaciones y publicador."""

from datetime import datetime, timezone

import pytest

from clientes import ClienteHttp, ProgresoRemoto, ServicioNoDisponible
from dominio.reporte import armar_reporte, fecha_iso
from fabricas import crear_publicador
from notificaciones import CADUCIDAD_SEGUNDOS, NotificacionesRedis
from tests.conftest import PROGRESO, USUARIO

# ---------------------------------------------------------------- dominio


def test_armar_reporte_deja_fuera_los_contadores_internos():
    reporte = armar_reporte(PROGRESO, datetime(2026, 10, 26, 20, 0, tzinfo=timezone.utc))

    assert "errores_frecuentes" not in reporte
    assert "aciertos_consecutivos" not in reporte
    assert reporte["generado_en"] == "2026-10-26T20:00:00Z"


def test_fecha_iso_sin_zona_se_toma_como_utc():
    assert fecha_iso(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05Z"


# ---------------------------------------------------------------- cliente


def transporte(respuestas):
    llamadas = []

    def llamar(metodo, url, cuerpo, timeout):
        llamadas.append(url)
        respuesta = respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    return llamar, llamadas


def test_progreso_remoto_devuelve_el_json():
    llamar, llamadas = transporte([(200, '{"usuario_id": "x"}')])
    progreso = ProgresoRemoto(ClienteHttp("http://flask_progreso:5000/", reintentos=0,
                                          transporte=llamar))

    assert progreso.obtener(USUARIO) == {"usuario_id": "x"}
    assert llamadas == [f"http://flask_progreso:5000/api/v2/progreso/{USUARIO}/"]


def test_sin_reintentos_http_un_solo_intento():
    llamar, llamadas = transporte([ConnectionRefusedError("rechazada")])
    progreso = ProgresoRemoto(ClienteHttp("http://p", reintentos=0, transporte=llamar))

    with pytest.raises(ServicioNoDisponible):
        progreso.obtener(USUARIO)
    assert len(llamadas) == 1


@pytest.mark.parametrize("respuesta", [(200, "[1, 2]"), (502, "<html>"), (200, "<html>")])
def test_respuestas_invalidas_son_servicio_no_disponible(respuesta):
    llamar, _ = transporte([respuesta])
    progreso = ProgresoRemoto(ClienteHttp("http://p", reintentos=0, transporte=llamar))

    with pytest.raises(ServicioNoDisponible):
        progreso.obtener(USUARIO)


# ---------------------------------------------------------------- notificaciones en Redis


class PipelineFalso:
    def __init__(self, registro):
        self.registro = registro

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __getattr__(self, orden):
        return lambda *args: self.registro.append((orden, *args))


class RedisConPipeline:
    def __init__(self):
        self.registro = []
        self.transaccion = None

    def pipeline(self, transaction):
        self.transaccion = transaction
        return PipelineFalso(self.registro)


def test_notificaciones_redis_lpush_ltrim_expire_en_transaccion():
    cliente = RedisConPipeline()

    NotificacionesRedis(cliente).agregar(USUARIO, {"sesion_id": 1, "tipo": "sesion_lista"})

    clave = f"notificaciones:{USUARIO}"
    assert cliente.transaccion is True
    assert cliente.registro == [
        ("lpush", clave, '{"sesion_id": 1, "tipo": "sesion_lista"}'),
        ("ltrim", clave, 0, 19),
        ("expire", clave, CADUCIDAD_SEGUNDOS),
        ("execute",),
    ]
    assert CADUCIDAD_SEGUNDOS == 604800


# ---------------------------------------------------------------- publicador


def test_publicador_sin_backend_ni_reintentos():
    publicador = crear_publicador({"REDIS_URL": "redis://redis:6379/0", "REDIS_TIMEOUT": 1.0})
    conf = publicador.conf

    # Sin backend de resultados: no abre suscripciones pub/sub al publicar.
    assert conf.result_backend is None
    assert conf.task_publish_retry is False
    assert conf.broker_connection_timeout == 1.0
    assert conf.broker_transport_options["socket_connect_timeout"] == 1.0
