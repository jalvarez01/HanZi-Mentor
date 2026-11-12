"""Adaptador de VaultDrop con su respuesta real, sin salir a la red."""

from decimal import Decimal

import pytest

from adaptadores.fabrica import crear_proveedor
from adaptadores.falso import CajasFalsas
from adaptadores.vaultdrop import AdaptadorVaultDrop
from dominio.puertos import AliadoNoDisponible

# Misma forma que GET /api/v2/catalogo/ de VaultDrop
# (services/catalog_service/repository.py en su repo).
CATALOGO = [
    {
        "id": 3,
        "nombre": "Caja Dragón",
        "imagen_url": "/static/core/images/catalog/caja-dragon.png",
        "descripcion": "",
        "precio": "25.00",
        "activa": True,
        "items": [
            {
                "item": {
                    "id": 1,
                    "nombre": "AK-47 | Redline",
                    "imagen_url": "/static/core/images/catalog/skin-1.png",
                    "rareza": "classified",
                    "valor_estimado": "85.00",
                },
                "probabilidad": "20.00",
            },
            {
                "item": {
                    "id": 2,
                    "nombre": "AWP | Dragon Lore",
                    "imagen_url": "",
                    "rareza": "contraband",
                    "valor_estimado": "850.00",
                },
                "probabilidad": "0.50",
            },
        ],
    }
]


def adaptador(respuesta=None, error=None):
    pedidas = []

    def obtener(url, timeout):
        pedidas.append((url, timeout))
        if error:
            raise error
        return respuesta

    return AdaptadorVaultDrop("http://10.0.0.5/", 3, obtener=obtener), pedidas


def test_pide_el_catalogo_publico_con_su_timeout():
    a, pedidas = adaptador(CATALOGO)

    a.obtener_cajas()

    assert pedidas == [("http://10.0.0.5/api/v2/catalogo/", 3)]


def test_traduce_la_respuesta_al_dominio():
    (caja,) = adaptador(CATALOGO)[0].obtener_cajas()

    assert (caja.id, caja.nombre, caja.precio) == (3, "Caja Dragón", "25.00")
    assert caja.imagen_url == "http://10.0.0.5/static/core/images/catalog/caja-dragon.png"
    ak, awp = caja.items
    assert (ak.nombre, ak.rareza, ak.valor_estimado) == ("AK-47 | Redline", "classified", "85.00")
    assert ak.probabilidad == Decimal("20.00")
    assert ak.imagen_url == "http://10.0.0.5/static/core/images/catalog/skin-1.png"
    assert awp.imagen_url == ""
    assert awp.probabilidad == Decimal("0.50")


def test_falla_de_red():
    a, _ = adaptador(error=AliadoNoDisponible("timeout"))

    with pytest.raises(AliadoNoDisponible):
        a.obtener_cajas()


@pytest.mark.parametrize("respuesta", [{"error": "x"}, [{"nombre": "sin id"}], [{"id": 1, "nombre": "x", "items": [{"item": {}}]}]])
def test_respuesta_inesperada(respuesta):
    with pytest.raises(AliadoNoDisponible):
        adaptador(respuesta)[0].obtener_cajas()


def test_sin_url_no_arranca():
    with pytest.raises(ValueError, match="ALIADO_URL"):
        AdaptadorVaultDrop("", 3)


def test_fabrica():
    base = {"ALIADO_URL": "http://10.0.0.5", "ALIADO_TIMEOUT": 3}

    assert isinstance(crear_proveedor({**base, "ALIADO_PROVEEDOR": "vaultdrop"}), AdaptadorVaultDrop)
    assert isinstance(crear_proveedor({**base, "ALIADO_PROVEEDOR": "falso"}), CajasFalsas)
    with pytest.raises(ValueError):
        crear_proveedor({**base, "ALIADO_PROVEEDOR": "otro"})
