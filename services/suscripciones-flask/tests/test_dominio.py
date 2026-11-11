"""Reglas del ciclo de vida, sin Flask ni base de datos."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from dominio import suscripcion as reglas
from dominio.excepciones import AccionNoPermitida
from tests.conftest import INICIO


def guardada(estado="activa", dias=30, plan="premium"):
    return SimpleNamespace(plan=plan, estado=estado, vence_en=INICIO + timedelta(days=dias))


def codigo(accion, estado):
    with pytest.raises(AccionNoPermitida) as error:
        reglas.verificar(accion, estado)
    return error.value.codigo


def test_sin_suscripcion_es_free_y_solo_puede_activar():
    estado = reglas.estado_actual(None, INICIO)

    assert (estado.plan, estado.estado, estado.vence_en) == ("free", "activa", None)
    assert estado.acciones == ("activar",)
    assert estado.nivel_maximo == 3


def test_premium_activa_puede_renovar_y_cancelar():
    estado = reglas.estado_actual(guardada(dias=30), INICIO)

    assert (estado.plan, estado.estado) == ("premium", "activa")
    assert estado.acciones == ("renovar", "cancelar")
    assert estado.nivel_maximo == 6


def test_con_mas_de_un_periodo_por_delante_no_se_renueva():
    estado = reglas.estado_actual(guardada(dias=45), INICIO)

    assert estado.acciones == ("cancelar",)
    assert codigo("renovar", estado) == "RENOVACION_ANTICIPADA"


def test_cancelada_sigue_premium_hasta_vencer():
    estado = reglas.estado_actual(guardada(estado="cancelada", dias=10), INICIO)

    assert (estado.plan, estado.estado) == ("premium", "cancelada")
    assert estado.acciones == ("renovar",)
    assert codigo("cancelar", estado) == "YA_CANCELADA"


@pytest.mark.parametrize("estado_guardado", ["activa", "cancelada"])
def test_vencida_vuelve_a_free(estado_guardado):
    vencida = guardada(estado=estado_guardado, dias=0)

    estado = reglas.estado_actual(vencida, INICIO)

    assert (estado.plan, estado.estado) == ("free", "vencida")
    assert estado.vence_en == vencida.vence_en
    assert estado.acciones == ("activar",)
    assert codigo("renovar", estado) == "SIN_PREMIUM"
    assert codigo("cancelar", estado) == "SIN_PREMIUM"


def test_activar_con_premium_vigente():
    assert codigo("activar", reglas.estado_actual(guardada(), INICIO)) == "YA_ES_PREMIUM"


def test_free_no_renueva_ni_cancela():
    estado = reglas.estado_actual(None, INICIO)

    assert codigo("renovar", estado) == "SIN_PREMIUM"
    assert codigo("cancelar", estado) == "SIN_PREMIUM"


def test_renovar_suma_el_periodo_a_lo_que_queda():
    quedan_diez = INICIO + timedelta(days=10)
    ya_vencio = INICIO - timedelta(days=3)

    assert reglas.vencimiento_al_renovar(quedan_diez, INICIO) == INICIO + timedelta(days=40)
    assert reglas.vencimiento_al_renovar(ya_vencio, INICIO) == INICIO + timedelta(days=30)
    assert reglas.vencimiento_al_activar(INICIO) == INICIO + timedelta(days=30)
