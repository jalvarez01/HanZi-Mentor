"""Fixtures comunes: app con SQLite en memoria y dobles de las dependencias.

Los dobles reemplazan a los clientes HTTP (catálogo y progreso), igual que
en agente-tutor/tutor/tests.py: el servicio se prueba sin red.
"""

import uuid

import pytest

from app import create_app
from i18n import compilar_traducciones
from fabricas import Dependencias
from motores import MotorTutor

USUARIO = uuid.UUID("12345678-1234-5678-1234-567812345678")


class MotorFalso(MotorTutor):
    # Hereda generar_ejercicio_adaptado (RF-IA-03) tal cual lo usa el servicio.
    def sugerir_dificultad(self, progreso):
        return 3

    def seleccionar_caracteres_nuevos(self, progreso, cantidad):
        return ["学", "校", "老", "师"][:cantidad]


class NotificadorEspia:
    def __init__(self):
        self.llamadas = []

    def sesion_lista(self, usuario_id, sesion):
        self.llamadas.append((usuario_id, sesion.id))


class ProgresoFalso:
    """Imita a progreso-flask: lleva la racha y la tasa como el servicio real."""

    def __init__(self, nivel_max=2, refuerzos=("目", "且"), caido=False, vencidos=(), patrones=()):
        self.nivel_max = nivel_max
        self.refuerzos = list(refuerzos)
        self.caido = caido
        # RF-IA-02: repasos vencidos y las curvas pedidas al cerrar.
        self.vencidos = list(vencidos)
        # RF-IA-03: patrones de error como los devuelve GET .../patrones/.
        self.patrones = list(patrones)
        self.curvas = []
        self.respuestas = []
        # El codigo_error de cada respuesta, en el mismo orden (RF-IA-01).
        self.codigos = []
        self.rachas = {}
        self.tasa = 0.5

    def obtener(self, usuario_id):
        return {
            "nivel_hsk": 2,
            "nivel_max_desbloqueado": self.nivel_max,
            "tasa_acierto": 0.7,
            "caracteres_dominados": [],
        }

    def caracteres_a_reforzar(self, usuario_id, limite=3):
        return self.refuerzos[:limite]

    def repasos_vencidos(self, usuario_id, limite=4):
        return [] if self.caido else self.vencidos[:limite]

    def patrones_de_error(self, usuario_id):
        return [] if self.caido else list(self.patrones)

    def aplicar_curva_olvido(self, usuario_id, sesion_id, cerrada_en, respuestas):
        self.curvas.append((usuario_id, sesion_id, cerrada_en, respuestas))
        if self.caido:
            return None
        return {"aplicada": True}

    def registrar_respuesta(self, usuario_id, caracter, acerto, codigo_error=None):
        self.respuestas.append((usuario_id, caracter, acerto))
        self.codigos.append(codigo_error)
        if self.caido:
            return None
        self.rachas[caracter] = self.rachas.get(caracter, 0) + 1 if acerto else 0
        self.tasa = round(self.tasa + 0.1 * ((1.0 if acerto else 0.0) - self.tasa), 4)
        return {"tasa_acierto": self.tasa, "aciertos_consecutivos": dict(self.rachas)}


@pytest.fixture
def progreso():
    return ProgresoFalso()


@pytest.fixture
def notificador():
    return NotificadorEspia()


@pytest.fixture
def app(progreso, notificador):
    deps = Dependencias(motor=MotorFalso(), notificador=notificador, progreso=progreso)
    return create_app({"TESTING": True, "DATABASE_URL": "sqlite://"}, dependencias=deps)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sesion_db(app):
    sesion = app.extensions["db"]["fabrica"]()
    yield sesion
    sesion.close()


@pytest.fixture
def crear_sesion(client):
    def crear(nivel_hsk=2, usuario=USUARIO, **otros):
        resp = client.post(
            "/api/v2/sesiones/",
            json={"usuario_id": str(usuario), "nivel_hsk": nivel_hsk, **otros},
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        return resp.get_json()

    return crear


def pytest_configure(config):
    # Las pruebas de idioma necesitan los .mo. No se suben al repo: en Docker
    # los genera `pybabel compile` y acá se compilan antes de empezar.
    compilar_traducciones()
