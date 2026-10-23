"""Pruebas del estándar común: health y errores en JSON.

Versión sin base de datos de services/flask-base/tests/test_base.py.
"""

import pytest
from flask import abort

from app import create_app
from errores import ErrorDominio


def crear(**config):
    datos = {"TESTING": True, "SERVICE_NAME": "servicio-prueba", "PROVEEDOR_EJEMPLOS": "falso"}
    datos.update(config)
    app = create_app(datos)

    @app.get("/falla")
    def falla():
        raise RuntimeError("secreto interno")

    @app.get("/dominio")
    def dominio():
        raise ErrorDominio("El nivel debe estar entre 1 y 6", "NIVEL_INVALIDO")

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


def test_404_devuelve_json(client):
    assert_error_json(client.get("/no/existe"), 404, "NO_ENCONTRADO")


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

    assert_error_json(resp, 400, "NIVEL_INVALIDO")
    assert resp.get_json()["error"] == "El nivel debe estar entre 1 y 6"


def test_config_desde_entorno(monkeypatch):
    monkeypatch.setenv("SERVICE_NAME", "desde-entorno")
    monkeypatch.setenv("PORT", "5099")
    monkeypatch.setenv("FLASK_DEBUG", "1")
    monkeypatch.setenv("PROVEEDOR_EJEMPLOS", "FALSO")

    app = create_app()

    assert app.config["SERVICE_NAME"] == "desde-entorno"
    assert app.config["PORT"] == 5099
    assert app.config["FLASK_DEBUG"] is True
    assert app.config["PROVEEDOR_EJEMPLOS"] == "falso"
