"""Fixtures comunes: una app con SQLite en memoria y una sesión para preparar datos."""

import pytest

from app import create_app
from i18n import compilar_traducciones

USUARIO = "12345678-1234-5678-1234-567812345678"


@pytest.fixture
def app():
    return create_app({"TESTING": True, "DATABASE_URL": "sqlite://"})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sesion(app):
    sesion = app.extensions["db"]["fabrica"]()
    yield sesion
    sesion.close()


@pytest.fixture
def responder(client):
    """POST de una respuesta; devuelve el JSON del progreso actualizado."""

    def enviar(caracter, acerto, usuario=USUARIO):
        resp = client.post(
            f"/api/v2/progreso/{usuario}/respuestas/",
            json={"caracter": caracter, "acerto": acerto},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return resp.get_json()

    return enviar


def pytest_configure(config):
    # Las pruebas de idioma necesitan los .mo. No se suben al repo: en Docker
    # los genera `pybabel compile` y acá se compilan antes de empezar.
    compilar_traducciones()
