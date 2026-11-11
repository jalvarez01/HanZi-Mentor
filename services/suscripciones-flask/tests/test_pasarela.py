"""Pasarela simulada, fábrica y validación de la tarjeta."""

import pytest

from dominio.excepciones import PagoRechazado, PasarelaNoDisponible
from errores import ErrorDominio
from pasarelas.base import Cobro, Tarjeta
from pasarelas.fabrica import crear_pasarela
from pasarelas.simulada import PasarelaSimulada
from tests.conftest import INICIO, pago
from validacion import luhn_valido, validar_activacion


def tarjeta(numero="4242424242424242"):
    return Tarjeta(numero=numero, titular="Ana", mes=12, anio=2030, cvc="123")


def cobrar(numero):
    return PasarelaSimulada().cobrar(Cobro("u", 14900, "COP", "activacion", tarjeta(numero)))


def test_aprueba_con_referencia():
    assert cobrar("4242424242424242").referencia.startswith("SIM-")


@pytest.mark.parametrize(
    "numero, codigo",
    [("4000000000000002", "TARJETA_RECHAZADA"), ("4000000000009995", "FONDOS_INSUFICIENTES")],
)
def test_rechaza(numero, codigo):
    with pytest.raises(PagoRechazado) as error:
        cobrar(numero)
    assert error.value.codigo == codigo
    assert error.value.estado == 402


def test_no_responde():
    with pytest.raises(PasarelaNoDisponible) as error:
        cobrar("4000000000000119")
    assert (error.value.codigo, error.value.estado) == ("PASARELA_NO_DISPONIBLE", 503)


def test_fabrica():
    assert isinstance(crear_pasarela("simulada"), PasarelaSimulada)
    with pytest.raises(ValueError):
        crear_pasarela("stripe")


def test_la_tarjeta_nunca_muestra_el_numero_completo():
    t = tarjeta()

    assert repr(t) == "Tarjeta(visa ****4242)"
    assert "4242424242424242" not in repr(Cobro("u", 1, "COP", "activacion", t))


@pytest.mark.parametrize(
    "numero, marca",
    [("4242424242424242", "visa"), ("5555555555554444", "mastercard"),
     ("378282246310005", "amex"), ("6011111111111117", "otra")],
)
def test_marca(numero, marca):
    assert tarjeta(numero).marca == marca


def test_luhn():
    assert luhn_valido("4242424242424242")
    assert not luhn_valido("4242424242424241")


def invalida(**cambios):
    with pytest.raises(ErrorDominio) as error:
        validar_activacion({"plan": "premium", "pago": pago(**cambios)}, INICIO)
    assert error.value.codigo == "ENTRADA_INVALIDA"
    return error.value.mensaje


def test_acepta_espacios_y_guiones_en_el_numero():
    t = validar_activacion({"plan": "premium", "pago": pago("4242-4242 4242-4242")}, INICIO)

    assert t.numero == "4242424242424242"
    assert (t.mes, t.anio) == (12, 2030)


def test_titular_con_espacios_de_mas():
    t = validar_activacion({"plan": "premium", "pago": pago(titular="  Ana   Pérez ")}, INICIO)

    assert t.titular == "Ana Pérez"


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"numero": "4242424242424241"}, "El número de tarjeta no es válido"),
        ({"numero": "4242"}, "El número de tarjeta no es válido"),
        ({"numero": "4242abcd42424242"}, "El número de tarjeta no es válido"),
        ({"numero": 4242424242424242}, "El número de tarjeta es obligatorio"),
        ({"titular": "A"}, "El nombre del titular debe tener entre 2 y 60 caracteres"),
        ({"titular": None}, "El nombre del titular debe tener entre 2 y 60 caracteres"),
        ({"vencimiento": "13/30"}, "El vencimiento debe tener el formato MM/AA"),
        ({"vencimiento": "2030-12"}, "El vencimiento debe tener el formato MM/AA"),
        ({"vencimiento": "10/26"}, "La tarjeta está vencida"),
        ({"cvc": "12"}, "El código de seguridad debe tener 3 o 4 dígitos"),
        ({"cvc": 123}, "El código de seguridad debe tener 3 o 4 dígitos"),
    ],
)
def test_tarjeta_invalida(cambios, mensaje):
    assert invalida(**cambios) == mensaje


def test_vence_este_mes_todavia_vale():
    # INICIO es noviembre de 2026: 11/26 vale hasta el 30 de noviembre.
    t = validar_activacion({"plan": "premium", "pago": pago(vencimiento="11/26")}, INICIO)

    assert (t.mes, t.anio) == (11, 2026)


@pytest.mark.parametrize("cuerpo", [None, [], {"plan": "free", "pago": pago()}, {"pago": pago()}])
def test_activacion_sin_plan_premium(cuerpo):
    with pytest.raises(ErrorDominio):
        validar_activacion(cuerpo, INICIO)
