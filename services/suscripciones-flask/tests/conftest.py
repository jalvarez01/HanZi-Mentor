"""Fixtures comunes: app con SQLite en memoria, reloj fijo y tarjetas de prueba."""

from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from i18n import compilar_traducciones

USUARIO = "12345678-1234-5678-1234-567812345678"
OTRO = "87654321-4321-8765-4321-876543210987"
URL = f"/api/v2/suscripciones/{USUARIO}/"
EN = {"Accept-Language": "en-US,en;q=0.9"}

# Tarjetas de prueba de la pasarela simulada (pasarelas/simulada.py).
APROBADA = "4242 4242 4242 4242"
RECHAZADA = "4000 0000 0000 0002"
SIN_FONDOS = "4000 0000 0000 9995"
NO_RESPONDE = "4000 0000 0000 0119"

INICIO = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)


def pago(numero=APROBADA, **cambios):
    datos = {"numero": numero, "titular": "Ana Pérez", "vencimiento": "12/30", "cvc": "123"}
    datos.update(cambios)
    return datos


class Reloj:
    """Hora que controla la prueba: así se puede hacer vencer un Premium."""

    def __init__(self):
        self.momento = INICIO

    def __call__(self):
        return self.momento

    def avanzar(self, **delta):
        self.momento += timedelta(**delta)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def app(reloj):
    return create_app({"TESTING": True, "DATABASE_URL": "sqlite://", "RELOJ": reloj})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def activar(client):
    def enviar(numero=APROBADA, usuario=USUARIO, **cambios):
        return client.post(
            f"/api/v2/suscripciones/{usuario}/activar/",
            json={"plan": "premium", "pago": pago(numero, **cambios)},
        )

    return enviar


@pytest.fixture
def renovar(client):
    def enviar(numero=APROBADA, usuario=USUARIO):
        return client.post(
            f"/api/v2/suscripciones/{usuario}/renovar/", json={"pago": pago(numero)}
        )

    return enviar


def pytest_configure(config):
    # Las pruebas de idioma necesitan los .mo: no se suben al repo.
    compilar_traducciones()
