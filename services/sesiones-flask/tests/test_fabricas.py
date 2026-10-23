"""Fábricas: solo MOCK y CONSOLE; una opción inexistente falla al arrancar."""

import pytest

from app import create_app
from clientes import CatalogoRemoto, ProgresoRemoto
from motores import MotorTutorMock
from notificadores import NotificadorConsola


def test_arma_las_dependencias_por_defecto():
    deps = create_app({"DATABASE_URL": "sqlite://"}).extensions["dependencias"]

    assert isinstance(deps.motor, MotorTutorMock)
    assert isinstance(deps.motor._catalogo, CatalogoRemoto)
    assert isinstance(deps.notificador, NotificadorConsola)
    assert isinstance(deps.progreso, ProgresoRemoto)


def test_urls_y_timeout_desde_el_entorno(monkeypatch):
    monkeypatch.setenv("CATALOGO_URL", "http://flask_catalogo:5000/")
    monkeypatch.setenv("PROGRESO_URL", "http://flask_progreso:5000")
    monkeypatch.setenv("HTTP_TIMEOUT", "1.5")
    monkeypatch.setenv("HTTP_REINTENTOS", "4")

    deps = create_app({"DATABASE_URL": "sqlite://"}).extensions["dependencias"]

    cliente_catalogo = deps.motor._catalogo._cliente
    assert cliente_catalogo.base_url == "http://flask_catalogo:5000"
    assert (cliente_catalogo.timeout, cliente_catalogo.reintentos) == (1.5, 4)
    assert deps.progreso._cliente.base_url == "http://flask_progreso:5000"


@pytest.mark.parametrize("clave, valor", [("TUTOR_ENGINE", "REAL"), ("NOTIFICADOR", "EMAIL")])
def test_opcion_no_disponible_falla_al_arrancar(clave, valor):
    with pytest.raises(ValueError, match=valor):
        create_app({"DATABASE_URL": "sqlite://", clave: valor})


def test_motor_mock_reglas_de_dificultad():
    motor = MotorTutorMock(catalogo=None)

    assert motor.sugerir_dificultad({"tasa_acierto": 0.9}) == 4
    assert motor.sugerir_dificultad({"tasa_acierto": 0.6}) == 3
    assert motor.sugerir_dificultad({"tasa_acierto": 0.3}) == 2
    assert motor.sugerir_dificultad({}) == 2


def test_motor_mock_pide_al_catalogo_el_nivel_del_progreso_sin_dominados():
    pedidos = []

    class Catalogo:
        def caracteres_de_nivel(self, nivel, excluir, cantidad):
            pedidos.append((nivel, excluir, cantidad))
            return ["人"]

    motor = MotorTutorMock(catalogo=Catalogo())

    assert motor.seleccionar_caracteres_nuevos({"nivel_hsk": 2, "caracteres_dominados": ["学"]}, 4) == ["人"]
    assert pedidos == [(2, ["学"], 4)]
