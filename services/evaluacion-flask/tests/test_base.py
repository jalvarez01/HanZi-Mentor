"""Pruebas del estándar común: health, errores en JSON y configuración."""

import pytest
from flask import abort

from app import create_app
from errores import ErrorDominio


def crear(**config):
    datos = {"TESTING": True, "SERVICE_NAME": "servicio-prueba"}
    datos.update(config)
    app = create_app(datos)

    @app.get("/falla")
    def falla():
        raise RuntimeError("secreto interno")

    @app.get("/dominio")
    def dominio():
        raise ErrorDominio("La dificultad debe estar entre 1 y 5", "DIFICULTAD_INVALIDA")

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


def test_health_no_depende_de_catalogo_ni_trazos():
    # Las URL apuntan a puertos cerrados: /health igual responde 200.
    app = crear(CATALOGO_URL="http://127.0.0.1:9", TRAZOS_URL="http://127.0.0.1:9")

    assert app.test_client().get("/health").status_code == 200


def test_404_devuelve_json(client):
    assert_error_json(client.get("/no/existe"), 404, "NO_ENCONTRADO")


def test_405_devuelve_json(client):
    assert_error_json(client.post("/health"), 405, "METODO_NO_PERMITIDO")


def test_405_en_get_de_evaluacion(client):
    assert_error_json(client.get("/api/v2/evaluacion/"), 405, "METODO_NO_PERMITIDO")


def test_400_devuelve_json(client):
    assert_error_json(client.get("/abortar"), 400, "ENTRADA_INVALIDA")


def test_500_no_filtra_detalles(client):
    resp = client.get("/falla")

    assert_error_json(resp, 500, "ERROR_INTERNO")
    assert resp.get_json()["error"] == "Error interno"
    assert "secreto" not in resp.get_data(as_text=True)


def test_error_dominio_devuelve_400(client):
    resp = client.get("/dominio")

    assert_error_json(resp, 400, "DIFICULTAD_INVALIDA")
    assert resp.get_json()["error"] == "La dificultad debe estar entre 1 y 5"


def test_config_desde_entorno(monkeypatch):
    monkeypatch.setenv("SERVICE_NAME", "desde-entorno")
    monkeypatch.setenv("PORT", "5099")
    monkeypatch.setenv("FLASK_DEBUG", "1")
    monkeypatch.setenv("CATALOGO_URL", "http://flask_catalogo:5000")
    monkeypatch.setenv("TRAZOS_URL", "http://flask_trazos:5000")
    monkeypatch.setenv("HTTP_TIMEOUT", "1.5")
    monkeypatch.setenv("HTTP_REINTENTOS", "0")

    app = create_app()

    assert app.config["SERVICE_NAME"] == "desde-entorno"
    assert app.config["PORT"] == 5099
    assert app.config["FLASK_DEBUG"] is True
    assert "DATABASE_URL" not in app.config
    deps = app.extensions["dependencias"]
    assert deps.catalogo._cliente.base_url == "http://flask_catalogo:5000"
    assert deps.trazos._cliente.base_url == "http://flask_trazos:5000"
    assert deps.catalogo._cliente.timeout == 1.5
    assert deps.catalogo._cliente.reintentos == 0
