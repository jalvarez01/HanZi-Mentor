"""Fixtures comunes: app con un Redis falso.

Las pruebas no necesitan un Redis real: el cliente se inyecta en
create_app, igual que los dobles de los clientes HTTP en los otros
servicios.
"""

import pytest
import redis

from app import create_app
from i18n import compilar_traducciones


class RedisFalso:
    def __init__(self, caido=False):
        self.caido = caido

    def ping(self):
        if self.caido:
            raise redis.ConnectionError("Redis caído")
        return True


@pytest.fixture
def redis_falso():
    return RedisFalso()


@pytest.fixture
def app(redis_falso):
    return create_app({"TESTING": True, "SERVICE_NAME": "servicio-prueba"},
                      redis_cliente=redis_falso)


@pytest.fixture
def client(app):
    return app.test_client()


def pytest_configure(config):
    # Las pruebas de idioma necesitan los .mo. No se suben al repo: en Docker
    # los genera `pybabel compile` y acá se compilan antes de empezar.
    compilar_traducciones()
