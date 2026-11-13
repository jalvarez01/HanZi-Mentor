"""Rutas por HTTP, errores en JSON e idioma."""

from pathlib import Path

import pytest
from babel.messages.extract import extract_from_dir
from babel.messages.pofile import read_po

from app import create_app
from dominio.puertos import AliadoNoDisponible, ProveedorCajas
from adaptadores.falso import CAJAS

EN = {"Accept-Language": "en"}
RAIZ = Path(__file__).resolve().parents[1]


class Caido(ProveedorCajas):
    nombre = "vaultdrop"

    def obtener_cajas(self):
        raise AliadoNoDisponible("caído")


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


def test_health(client):
    assert client.get("/health").get_json() == {"estado": "ok", "servicio": "aliado-flask"}


def test_listar_cajas(client):
    resp = client.get("/api/v2/aliado/cajas/")

    assert resp.status_code == 200
    datos = resp.get_json()
    assert (datos["aliado"], datos["proveedor"], datos["respaldo"]) == ("VaultDrop", "falso", False)
    assert [(c["id"], c["nombre"], c["items"]) for c in datos["cajas"]] == [
        (1, "Caja de prueba", 3),
        (2, "Caja legendaria de prueba", 3),
    ]


def test_abrir_caja(client):
    resp = client.post("/api/v2/aliado/cajas/1/abrir/")

    assert resp.status_code == 200
    datos = resp.get_json()
    assert list(datos) == ["aliado", "proveedor", "respaldo", "caja", "item"]
    assert datos["caja"] == {"id": 1, "nombre": "Caja de prueba", "precio": "10.00", "imagen_url": ""}
    assert datos["item"]["nombre"] in {i.nombre for i in CAJAS[0].items}
    assert set(datos["item"]) == {"nombre", "rareza", "valor_estimado", "imagen_url", "probabilidad"}


def test_caja_que_no_existe(client):
    resp = client.post("/api/v2/aliado/cajas/99/abrir/", headers=EN)

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Box not found.", "codigo": "NO_ENCONTRADO"}


def test_abrir_es_post(client):
    assert client.get("/api/v2/aliado/cajas/1/abrir/").status_code == 405


def test_aliado_caido_sin_respaldo_es_503_en_los_dos_idiomas():
    client = create_app({"TESTING": True}, proveedor=Caido()).test_client()

    es = client.get("/api/v2/aliado/cajas/")
    en = client.post("/api/v2/aliado/cajas/1/abrir/", headers=EN)

    assert es.status_code == en.status_code == 503
    assert es.get_json() == {
        "error": "VaultDrop no respondió. Intentá de nuevo en un momento.",
        "codigo": "ALIADO_NO_DISPONIBLE",
    }
    assert en.get_json()["error"] == "VaultDrop did not respond. Try again in a moment."


def test_todos_los_textos_tienen_traduccion_al_ingles():
    marcados = {
        mensaje
        for _, _, mensaje, _, _ in extract_from_dir(
            str(RAIZ),
            method_map=[("tests/**.py", "ignore"), ("**.py", "python")],
            keywords={"N_": None},
        )
    }
    with (RAIZ / "translations/en/LC_MESSAGES/messages.po").open("rb") as archivo:
        traducidos = {m.id for m in read_po(archivo) if m.id and m.string}

    assert marcados and marcados - traducidos == set()
