"""Pruebas del dominio de lecciones, sin base de datos ni Flask."""

import random

import pytest

from dominio.lecciones import EjercicioFactory, LeccionBuilder, TIPOS_EJERCICIO

DEL_NIVEL = ["你", "好", "我"]
SIN_CLASIFICAR = ["爱", "心"]


def construir(del_nivel, sin_clasificar, cantidad, semilla=1):
    return (
        LeccionBuilder(random.Random(semilla))
        .con_caracteres_del_nivel(del_nivel, sin_clasificar, cantidad=cantidad)
        .con_ejercicios_variados()
        .build()
    )


def test_prioriza_el_nivel_exacto():
    planes = construir(DEL_NIVEL, SIN_CLASIFICAR, cantidad=3)

    assert sorted(p.caracter for p in planes) == sorted(DEL_NIVEL)


def test_rellena_con_sin_clasificar_si_faltan():
    planes = construir(DEL_NIVEL, SIN_CLASIFICAR, cantidad=5)

    caracteres = [p.caracter for p in planes]
    assert len(caracteres) == 5
    assert set(caracteres[:3]) == set(DEL_NIVEL)
    assert set(caracteres[3:]) == set(SIN_CLASIFICAR)


def test_no_inventa_caracteres_si_no_alcanzan():
    assert len(construir(DEL_NIVEL, [], cantidad=10)) == 3


def test_tipos_de_ejercicio_validos():
    for plan in construir(DEL_NIVEL, SIN_CLASIFICAR, cantidad=5):
        assert plan.tipo in TIPOS_EJERCICIO


def test_no_modifica_las_listas_recibidas():
    del_nivel = list(DEL_NIVEL)
    construir(del_nivel, SIN_CLASIFICAR, cantidad=2)

    assert del_nivel == DEL_NIVEL


def test_factory_rechaza_tipo_invalido():
    with pytest.raises(ValueError):
        EjercicioFactory.crear(tipo="pinyin", caracter="你")
