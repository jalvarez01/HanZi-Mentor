"""Fixtures comunes: una app con SQLite en memoria y helpers para poblarla."""

import pytest

from app import create_app
from modelos import Caracter, Trazo

MEDIANA = [[458, 800], [435, 764], [400, 700], [350, 620], [300, 540]]


@pytest.fixture
def app():
    return create_app({"TESTING": True, "DATABASE_URL": "sqlite://"})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sesion(app):
    """Sesión fuera de las peticiones, para preparar datos."""
    sesion = app.extensions["db"]["fabrica"]()
    yield sesion
    sesion.close()


@pytest.fixture
def crear_caracter(sesion):
    def crear(hanzi, nivel_hsk=1, pinyin="", definicion="", trazos=0, **otros):
        caracter = Caracter(
            hanzi=hanzi, nivel_hsk=nivel_hsk, pinyin=pinyin, definicion=definicion, **otros
        )
        # Se agregan en orden inverso para comprobar que la API los ordena.
        caracter.trazos = [
            Trazo(secuencia=n, path_svg=f"M {n} 0 L {n} 10", mediana=MEDIANA)
            for n in range(trazos, 0, -1)
        ]
        sesion.add(caracter)
        sesion.commit()
        return caracter

    return crear
