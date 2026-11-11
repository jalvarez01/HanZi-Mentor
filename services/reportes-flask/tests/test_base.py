"""Pruebas del estándar común: health, errores en JSON y configuración."""

import pytest
from flask import abort

from app import create_app
from errores import ErrorDominio
from tests.conftest import RedisFalso


def crear(redis_cliente=None, **config):
    datos = {"TESTING": True, "SERVICE_NAME": "servicio-prueba"}
    datos.update(config)
    app = create_app(datos, redis_cliente=redis_cliente or RedisFalso())

    @app.get("/falla")
    def falla():
        raise RuntimeError("secreto interno")

    @app.get("/dominio")
    def dominio():
        raise ErrorDominio("El usuario_id debe ser un UUID válido", "ENTRADA_INVALIDA")

    @app.get("/abortar")
    def abortar():
        abort(400)

    return app


@pytest.fixture
def client():
    return crear().test_client()


def assert_error_json(resp, estado, codigo):
    assert resp.status_code == estado
    assert resp.is_json
    datos = resp.get_json()
    assert datos["codigo"] == codigo
    assert "error" in datos


def test_health(client):
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json() == {"estado": "ok", "servicio": "servicio-prueba"}


def test_health_503_si_redis_no_responde():
    client = crear(RedisFalso(caido=True)).test_client()

    resp = client.get("/health")

    assert_error_json(resp, 503, "COLA_NO_DISPONIBLE")
    assert resp.get_json()["error"] == "La cola de tareas no está disponible."


def test_health_503_en_ingles():
    client = crear(RedisFalso(caido=True)).test_client()

    resp = client.get("/health", headers={"Accept-Language": "en"})

    assert_error_json(resp, 503, "COLA_NO_DISPONIBLE")
    assert resp.get_json()["error"] == "The task queue is not available."


def test_health_con_redis_real_apagado():
    # Puerto cerrado: el cliente de verdad falla rápido y /health da 503.
    app = create_app({"TESTING": True, "REDIS_URL": "redis://127.0.0.1:9/0",
                      "REDIS_TIMEOUT": 0.5})

    assert_error_json(app.test_client().get("/health"), 503, "COLA_NO_DISPONIBLE")


def test_404_devuelve_json(client):
    assert_error_json(client.get("/no/existe"), 404, "NO_ENCONTRADO")


def test_404_en_ingles(client):
    resp = client.get("/no/existe", headers={"Accept-Language": "en"})

    assert resp.get_json()["error"] == "Resource not found"


def test_405_devuelve_json(client):
    assert_error_json(client.post("/health"), 405, "METODO_NO_PERMITIDO")


def test_400_devuelve_json(client):
    assert_error_json(client.get("/abortar"), 400, "ENTRADA_INVALIDA")


def test_500_no_filtra_detalles(client):
    resp = client.get("/falla")

    assert_error_json(resp, 500, "ERROR_INTERNO")
    assert resp.get_json()["error"] == "Error interno"
    assert "secreto" not in resp.get_data(as_text=True)


def test_error_dominio_devuelve_400(client):
    resp = client.get("/dominio")

    assert_error_json(resp, 400, "ENTRADA_INVALIDA")


def test_config_desde_entorno(monkeypatch):
    monkeypatch.setenv("SERVICE_NAME", "desde-entorno")
    monkeypatch.setenv("PORT", "5099")
    monkeypatch.setenv("FLASK_DEBUG", "1")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("REDIS_TIMEOUT", "2.5")

    app = create_app()

    assert app.config["SERVICE_NAME"] == "desde-entorno"
    assert app.config["PORT"] == 5099
    assert app.config["FLASK_DEBUG"] is True
    assert "DATABASE_URL" not in app.config
    opciones = app.extensions["redis"].connection_pool.connection_kwargs
    assert (opciones["host"], opciones["port"], opciones["db"]) == ("redis", 6379, 0)
    assert opciones["socket_timeout"] == 2.5
