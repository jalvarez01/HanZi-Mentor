"""Pruebas del estándar común: health, errores en JSON y sesión de base de datos."""

import pytest
from flask import abort
from sqlalchemy import text

from app import create_app
from db import obtener_sesion
from errores import ErrorDominio


def crear(**config):
    datos = {"TESTING": True, "SERVICE_NAME": "servicio-prueba", "DATABASE_URL": "sqlite://"}
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

    @app.get("/consulta")
    def consulta():
        return {"valor": obtener_sesion().execute(text("SELECT 1")).scalar()}

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


def test_health_con_db(client):
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json() == {"estado": "ok", "servicio": "servicio-prueba"}


def test_health_sin_db():
    resp = crear(DATABASE_URL="").test_client().get("/health")

    assert resp.status_code == 200
    assert resp.get_json()["estado"] == "ok"


def test_health_con_db_caida():
    app = crear(DATABASE_URL="sqlite:////ruta/que/no/existe/db.sqlite3")

    resp = app.test_client().get("/health")

    assert resp.status_code == 503
    assert resp.get_json() == {
        "estado": "error",
        "servicio": "servicio-prueba",
        "codigo": "DB_NO_DISPONIBLE",
    }


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


def test_error_dominio_con_otro_estado():
    app = crear()

    @app.get("/conflicto")
    def conflicto():
        raise ErrorDominio("Ya respondido", "YA_RESPONDIDO", estado=409)

    assert_error_json(app.test_client().get("/conflicto"), 409, "YA_RESPONDIDO")


def test_sesion_por_peticion(client):
    resp = client.get("/consulta")

    assert resp.status_code == 200
    assert resp.get_json() == {"valor": 1}


def test_config_desde_entorno(monkeypatch):
    monkeypatch.setenv("SERVICE_NAME", "desde-entorno")
    monkeypatch.setenv("PORT", "5099")
    monkeypatch.setenv("FLASK_DEBUG", "1")
    monkeypatch.setenv("DATABASE_URL", "")

    app = create_app()

    assert app.config["SERVICE_NAME"] == "desde-entorno"
    assert app.config["PORT"] == 5099
    assert app.config["FLASK_DEBUG"] is True
    assert app.config["DATABASE_URL"] is None


# ---------- idioma de los mensajes (T22) ----------


@pytest.mark.parametrize("cabecera, mensaje", [
    (None, "Recurso no encontrado"),
    ("es", "Recurso no encontrado"),
    ("es-CO,es;q=0.9", "Recurso no encontrado"),
    ("en", "Resource not found"),
    ("en-US,en;q=0.9", "Resource not found"),
    ("fr", "Recurso no encontrado"),
])
def test_404_en_el_idioma_de_accept_language(client, cabecera, mensaje):
    cabeceras = {"Accept-Language": cabecera} if cabecera else {}

    resp = client.get("/no/existe", headers=cabeceras)

    # Solo cambia el texto: el estado y el código son los mismos.
    assert resp.status_code == 404
    assert resp.get_json() == {"error": mensaje, "codigo": "NO_ENCONTRADO"}


def test_405_y_500_en_ingles(client):
    en = {"Accept-Language": "en"}

    assert client.post("/health", headers=en).get_json()["error"] == "Method not allowed"
    assert client.get("/falla", headers=en).get_json()["error"] == "Internal error"


def test_error_dominio_con_parametros():
    app = crear()

    @app.get("/limite")
    def limite():
        raise ErrorDominio("El límite debe ser como máximo %(maximo)s", "LIMITE_INVALIDO",
                           params={"maximo": 50})

    resp = app.test_client().get("/limite", headers={"Accept-Language": "en"})

    # Un texto que no está en el catálogo sale en español, con sus datos.
    assert resp.get_json() == {"error": "El límite debe ser como máximo 50", "codigo": "LIMITE_INVALIDO"}
    assert str(ErrorDominio("Hasta %(n)s", params={"n": 3})) == "Hasta 3"
