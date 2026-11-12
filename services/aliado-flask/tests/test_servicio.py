"""Sorteo, respaldo con el último catálogo y casos de uso."""

import random
from collections import Counter
from decimal import Decimal

import pytest

from adaptadores.falso import CAJAS
from dominio.caja import Caja, CajaSinItems, Item, sortear
from dominio.puertos import AliadoNoDisponible, ProveedorCajas
from errores import ErrorDominio
from servicio import CatalogoAliado, abrir_caja


class Reloj:
    def __init__(self):
        self.segundos = 0.0

    def __call__(self):
        return self.segundos


class Proveedor(ProveedorCajas):
    """Responde las cajas falsas hasta que se le pide fallar."""

    nombre = "prueba"

    def __init__(self):
        self.llamadas = 0
        self.falla = False

    def obtener_cajas(self):
        self.llamadas += 1
        if self.falla:
            raise AliadoNoDisponible("caído")
        return list(CAJAS)


# --- Sorteo ---

def test_sorteo_respeta_las_probabilidades():
    rng = random.Random(7)
    caja = CAJAS[1]  # 1 % Dragon Lore, 9 % Howl, 90 % Orion

    conteo = Counter(sortear(caja, rng).nombre for _ in range(5000))

    assert 4300 < conteo["USP-S | Orion"] < 4700
    assert 300 < conteo["M4A4 | Howl"] < 600
    assert conteo["AWP | Dragon Lore"] < 120


def test_items_con_probabilidad_cero_no_salen():
    caja = Caja(1, "c", "1", "", (
        Item("nunca", "x", "1", "", Decimal("0")),
        Item("siempre", "x", "1", "", Decimal("100")),
    ))

    assert {sortear(caja, random.Random(s)).nombre for s in range(50)} == {"siempre"}


def test_caja_sin_items():
    with pytest.raises(CajaSinItems):
        sortear(Caja(1, "vacía", "1", "", ()))


# --- Respaldo ---

def test_reutiliza_el_catalogo_mientras_esta_fresco():
    proveedor, reloj = Proveedor(), Reloj()
    catalogo = CatalogoAliado(proveedor, reloj=reloj, fresco_seg=60)

    catalogo.cajas()
    reloj.segundos = 59
    catalogo.cajas()

    assert proveedor.llamadas == 1


def test_despues_lo_vuelve_a_pedir():
    proveedor, reloj = Proveedor(), Reloj()
    catalogo = CatalogoAliado(proveedor, reloj=reloj, fresco_seg=60)

    catalogo.cajas()
    reloj.segundos = 61
    cajas, respaldo = catalogo.cajas()

    assert proveedor.llamadas == 2
    assert respaldo is False


def test_si_el_aliado_cae_usa_el_ultimo_catalogo():
    proveedor, reloj = Proveedor(), Reloj()
    catalogo = CatalogoAliado(proveedor, reloj=reloj, fresco_seg=60)
    catalogo.cajas()

    proveedor.falla = True
    reloj.segundos = 120
    cajas, respaldo = catalogo.cajas()

    assert respaldo is True
    assert [c.id for c in cajas] == [1, 2]


def test_sin_ningun_catalogo_es_503():
    proveedor = Proveedor()
    proveedor.falla = True

    with pytest.raises(ErrorDominio) as error:
        CatalogoAliado(proveedor).cajas()

    assert (error.value.estado, error.value.codigo) == (503, "ALIADO_NO_DISPONIBLE")


# --- Abrir ---

def test_abrir_caja():
    caja, item, respaldo = abrir_caja(CatalogoAliado(Proveedor()), 2, random.Random(1))

    assert caja.id == 2
    assert item in caja.items
    assert respaldo is False


def test_caja_que_no_existe():
    with pytest.raises(ErrorDominio) as error:
        abrir_caja(CatalogoAliado(Proveedor()), 99)

    assert (error.value.estado, error.value.codigo) == (404, "NO_ENCONTRADO")
