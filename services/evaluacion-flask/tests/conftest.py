"""Fixtures comunes: app con dobles del catálogo y de trazos.

Los dobles reemplazan a los clientes HTTP, igual que los `CatalogoFalso` de
agente-tutor/tutor/tests.py: el servicio se prueba sin red.
"""

import pytest

from app import create_app
from clientes import RespuestaRechazada, ServicioNoDisponible
from fabricas import Dependencias
from i18n import compilar_traducciones

MEDIANA_1 = [[458, 800], [435, 764], [400, 700], [350, 620], [300, 540]]

DETALLES = {
    "学": {
        "hanzi": "学",
        "pinyin": "xué",
        "definicion": "study, learning",
        "nivel_hsk": 1,
        "trazos": [
            {"secuencia": 1, "path_svg": "M 0 0", "mediana": MEDIANA_1},
            {"secuencia": 2, "path_svg": "M 1 1", "mediana": [[10, 10], [20, 20]]},
        ],
    },
    "人": {
        "hanzi": "人",
        "pinyin": "rén",
        "definicion": "man, person; people",
        "nivel_hsk": 1,
        "trazos": [],
    },
}

VEREDICTO = {
    "aprobado": True,
    "puntaje": 92,
    "motivo": "correcto",
    "detalle": "Trazo correcto.",
    "invertido": False,
    "puntos_lejanos": [],
}


class CatalogoFalso:
    def __init__(self, detalles=None, caido=False):
        self.detalles = DETALLES if detalles is None else detalles
        self.caido = caido
        self.consultas = []

    def obtener_detalle(self, hanzi):
        self.consultas.append(hanzi)
        if self.caido:
            raise ServicioNoDisponible("catálogo caído")
        if hanzi not in self.detalles:
            raise RespuestaRechazada("404", 404, {"error": "No encontrado", "codigo": "NO_ENCONTRADO"})
        return self.detalles[hanzi]


class TrazosFalso:
    def __init__(self, veredicto=None, caido=False, rechazo=None):
        self.veredicto = dict(VEREDICTO if veredicto is None else veredicto)
        self.caido = caido
        self.rechazo = rechazo
        self.llamadas = []

    def validar(self, mediana, puntos, ancho, alto):
        self.llamadas.append({"mediana": mediana, "puntos": puntos, "ancho": ancho, "alto": alto})
        if self.caido:
            raise ServicioNoDisponible("trazos caído")
        if self.rechazo:
            raise RespuestaRechazada("400", 400, self.rechazo)
        return self.veredicto


@pytest.fixture
def catalogo():
    return CatalogoFalso()


@pytest.fixture
def trazos():
    return TrazosFalso()


@pytest.fixture
def app(catalogo, trazos):
    deps = Dependencias(catalogo=catalogo, trazos=trazos)
    return create_app({"TESTING": True}, dependencias=deps)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def evaluar(client):
    def llamar(**cuerpo):
        return client.post("/api/v2/evaluacion/", json=cuerpo)

    return llamar


def pytest_configure(config):
    # Las pruebas de idioma necesitan los .mo. No se suben al repo: en Docker
    # los genera `pybabel compile` y acá se compilan antes de empezar.
    compilar_traducciones()
