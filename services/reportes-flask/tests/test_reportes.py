"""Endpoints de /api/v2/reportes/ con Celery en modo eager, sin Redis."""

import uuid

import pytest
import redis
from kombu.exceptions import OperationalError

import servicio
from app import create_app
from dominio.excepciones import ErrorReporte
from tareas import celery_app, notificar_sesion_lista
from tests.conftest import PROGRESO, USUARIO, ProgresoFalso, RedisFalso

DESCONOCIDO = "00000000-0000-4000-8000-000000000000"


def pedir(client, cuerpo, idioma=None):
    cabeceras = {"Accept-Language": idioma} if idioma else {}
    return client.post("/api/v2/reportes/", json=cuerpo, headers=cabeceras)


# ---------------------------------------------------------------- POST


def test_post_202_con_task_id_y_location(client, publicador):
    resp = pedir(client, {"usuario_id": USUARIO})

    assert resp.status_code == 202
    datos = resp.get_json()
    assert list(datos) == ["task_id", "estado"]
    assert datos["estado"] == "pendiente"
    assert uuid.UUID(datos["task_id"])
    assert resp.headers["Location"] == f"/api/v2/reportes/{datos['task_id']}/"
    assert publicador.enviadas == [("generar_reporte_progreso", [USUARIO])]


def test_post_y_get_hasta_listo(client):
    task_id = pedir(client, {"usuario_id": USUARIO}).get_json()["task_id"]

    resp = client.get(f"/api/v2/reportes/{task_id}/")

    assert resp.status_code == 200
    datos = resp.get_json()
    assert list(datos) == ["task_id", "estado", "resultado"]
    assert datos["estado"] == "listo"
    assert datos["resultado"]["usuario_id"] == USUARIO
    assert datos["resultado"]["tasa_acierto"] == PROGRESO["tasa_acierto"]
    assert datos["resultado"]["caracteres_debiles"][0] == {"caracter": "学", "fallos": 3}


@pytest.mark.parametrize("idioma, mensaje", [
    (None, "El usuario_id debe ser un UUID válido"),
    ("en", "The usuario_id must be a valid UUID"),
])
def test_post_uuid_invalido_400(client, idioma, mensaje):
    resp = pedir(client, {"usuario_id": "123"}, idioma)

    assert resp.status_code == 400
    assert resp.get_json() == {"error": mensaje, "codigo": "ENTRADA_INVALIDA"}


@pytest.mark.parametrize("cuerpo", [{}, {"usuario_id": 5}, {"otro": USUARIO}])
def test_post_sin_usuario_id_valido_400(client, cuerpo):
    resp = pedir(client, cuerpo)

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


@pytest.mark.parametrize("idioma, mensaje", [
    (None, "El cuerpo debe ser un objeto JSON"),
    ("en", "The body must be a JSON object"),
])
def test_post_cuerpo_no_json_400(client, idioma, mensaje):
    cabeceras = {"Accept-Language": idioma} if idioma else {}
    resp = client.post("/api/v2/reportes/", data="hola", headers=cabeceras)

    assert resp.status_code == 400
    assert resp.get_json() == {"error": mensaje, "codigo": "ENTRADA_INVALIDA"}


class PublicadorCaido:
    def send_task(self, *args, **kwargs):
        raise OperationalError("Error 111 connecting to redis:6379")


@pytest.mark.parametrize("idioma, mensaje", [
    (None, "La cola de tareas no está disponible."),
    ("en", "The task queue is not available."),
])
def test_post_503_si_redis_no_responde(idioma, mensaje):
    client = create_app({"TESTING": True}, redis_cliente=RedisFalso(),
                        publicador=PublicadorCaido()).test_client()

    resp = pedir(client, {"usuario_id": USUARIO}, idioma)

    assert resp.status_code == 503
    assert resp.get_json() == {"error": mensaje, "codigo": "COLA_NO_DISPONIBLE"}
    assert "6379" not in resp.get_data(as_text=True)


# ---------------------------------------------------------------- GET


def test_get_task_id_desconocido_es_pendiente(client):
    # Limitación de Celery: no distingue "no existe" de "todavía en la cola".
    resp = client.get(f"/api/v2/reportes/{DESCONOCIDO}/")

    assert resp.status_code == 200
    assert resp.get_json() == {"task_id": DESCONOCIDO, "estado": "pendiente"}


def test_get_task_id_invalido_400(client):
    resp = client.get("/api/v2/reportes/no-es-un-id/", headers={"Accept-Language": "en"})

    assert resp.status_code == 400
    assert resp.get_json() == {"error": "The task_id must be a valid UUID",
                               "codigo": "ENTRADA_INVALIDA"}


@pytest.mark.parametrize("idioma, mensaje", [
    (None, "El servicio de progreso no respondió. Probá de nuevo en unos segundos."),
    ("en", "The progress service did not respond. Try again in a few seconds."),
])
def test_tarea_fallida_devuelve_su_codigo_y_mensaje_traducido(client, dependencias, idioma, mensaje):
    # El error pasa por el backend como JSON y Celery recrea ErrorReporte.
    dependencias.progreso = ProgresoFalso(caido=True)
    task_id = pedir(client, {"usuario_id": USUARIO}).get_json()["task_id"]

    cabeceras = {"Accept-Language": idioma} if idioma else {}
    resp = client.get(f"/api/v2/reportes/{task_id}/", headers=cabeceras)

    assert resp.status_code == 200
    assert resp.get_json() == {
        "task_id": task_id,
        "estado": "error",
        "codigo": "DEPENDENCIA_NO_DISPONIBLE",
        "error": mensaje,
    }
    assert "Traceback" not in resp.get_data(as_text=True)


@pytest.mark.parametrize("idioma, mensaje", [
    (None, "No se pudo generar el reporte."),
    ("en", "The report could not be generated."),
])
def test_falla_inesperada_da_error_generico(client, dependencias, idioma, mensaje):
    class ProgresoRoto:
        def obtener(self, usuario_id):
            raise KeyError("detalle interno")

    dependencias.progreso = ProgresoRoto()
    task_id = pedir(client, {"usuario_id": USUARIO}).get_json()["task_id"]

    cabeceras = {"Accept-Language": idioma} if idioma else {}
    datos = client.get(f"/api/v2/reportes/{task_id}/", headers=cabeceras).get_json()

    assert (datos["estado"], datos["codigo"], datos["error"]) == ("error", "ERROR_INTERNO", mensaje)
    assert "detalle interno" not in str(datos)


class ResultadoFalso:
    def __init__(self, state, result=None):
        self.state = state
        self.result = result


class ResultadosFalsos:
    def __init__(self, state=None, result=None, caido=False):
        self.state, self.result, self.caido = state, result, caido

    def AsyncResult(self, task_id):
        if self.caido:
            raise redis.ConnectionError("Redis caído")
        return ResultadoFalso(self.state, self.result)


@pytest.mark.parametrize("estado_celery, estado", [
    ("PENDING", "pendiente"),
    ("RECEIVED", "pendiente"),
    ("STARTED", "en_proceso"),
    ("RETRY", "en_proceso"),
    ("SUCCESS", "listo"),
    ("FAILURE", "error"),
    ("REVOKED", "error"),
])
def test_estados_de_celery(client, monkeypatch, estado_celery, estado):
    monkeypatch.setattr(servicio, "celery_app", ResultadosFalsos(estado_celery, {}))

    datos = client.get(f"/api/v2/reportes/{DESCONOCIDO}/").get_json()

    assert datos["estado"] == estado


def test_error_reporte_con_codigo_propio(client, monkeypatch):
    error = ErrorReporte("OTRO_CODIGO", "Error interno")
    monkeypatch.setattr(servicio, "celery_app", ResultadosFalsos("FAILURE", error))

    datos = client.get(f"/api/v2/reportes/{DESCONOCIDO}/",
                       headers={"Accept-Language": "en"}).get_json()

    assert (datos["codigo"], datos["error"]) == ("OTRO_CODIGO", "Internal error")


def test_get_503_si_redis_no_responde(client, monkeypatch):
    monkeypatch.setattr(servicio, "celery_app", ResultadosFalsos(caido=True))

    resp = client.get(f"/api/v2/reportes/{DESCONOCIDO}/", headers={"Accept-Language": "en"})

    assert resp.status_code == 503
    assert resp.get_json() == {"error": "The task queue is not available.",
                               "codigo": "COLA_NO_DISPONIBLE"}


def test_resultados_reales_con_redis_apagado_fallan_rapido(monkeypatch):
    # Backend Redis de verdad contra un puerto cerrado: 503, no se cuelga.
    monkeypatch.setattr(celery_app.conf, "result_backend", "redis://127.0.0.1:9/0")
    if hasattr(celery_app._local, "backend"):
        del celery_app._local.backend
    client = create_app({"TESTING": True}, redis_cliente=RedisFalso()).test_client()

    resp = client.get(f"/api/v2/reportes/{DESCONOCIDO}/")

    assert resp.status_code == 503
    assert resp.get_json()["codigo"] == "COLA_NO_DISPONIBLE"


# ---------------------------------------------------------------- notificaciones


def test_notificaciones_del_usuario(client):
    notificar_sesion_lista.apply(args=[USUARIO, 1])
    notificar_sesion_lista.apply(args=[USUARIO, 2])

    resp = client.get(f"/api/v2/reportes/notificaciones/{USUARIO}/")

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["usuario_id"] == USUARIO
    assert [n["sesion_id"] for n in datos["notificaciones"]] == [2, 1]


def test_notificaciones_vacias(client):
    resp = client.get(f"/api/v2/reportes/notificaciones/{DESCONOCIDO}/")

    assert resp.get_json() == {"usuario_id": DESCONOCIDO, "notificaciones": []}


def test_notificaciones_uuid_invalido_400(client):
    resp = client.get("/api/v2/reportes/notificaciones/123/")

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_notificaciones_503_si_redis_no_responde():
    class Caidas:
        def listar(self, usuario_id):
            raise redis.ConnectionError("Redis caído")

    client = create_app({"TESTING": True}, redis_cliente=RedisFalso(),
                        notificaciones=Caidas()).test_client()

    resp = client.get(f"/api/v2/reportes/notificaciones/{USUARIO}/")

    assert resp.status_code == 503
    assert resp.get_json()["codigo"] == "COLA_NO_DISPONIBLE"


def test_get_reportes_405_en_post_de_task(client):
    resp = client.post(f"/api/v2/reportes/{DESCONOCIDO}/")

    assert resp.status_code == 405
    assert resp.get_json()["codigo"] == "METODO_NO_PERMITIDO"
