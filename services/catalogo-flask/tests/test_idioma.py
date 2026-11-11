"""T22: Accept-Language elige el idioma del mensaje; las claves, el código y
el estado no cambian. Sin cabecera, o con otro idioma, en español."""

import pytest

EN = {"Accept-Language": "en-US,en;q=0.9"}


@pytest.mark.parametrize("cabeceras, mensaje", [
    ({}, "Carácter no encontrado."),
    ({"Accept-Language": "es"}, "Carácter no encontrado."),
    ({"Accept-Language": "fr"}, "Carácter no encontrado."),
    (EN, "Character not found."),
])
def test_caracter_inexistente(client, cabeceras, mensaje):
    resp = client.get("/api/v2/caracteres/龘/", headers=cabeceras)

    assert resp.status_code == 404
    assert resp.get_json() == {"error": mensaje, "codigo": "NO_ENCONTRADO"}


def test_limite_invalido_con_su_maximo(client):
    es = client.get("/api/v2/caracteres/?limite=0")
    en = client.get("/api/v2/caracteres/?limite=0", headers=EN)

    assert (es.status_code, en.status_code) == (400, 400)
    assert es.get_json()["error"] == "El límite debe ser un entero entre 1 y 100"
    assert en.get_json() == {
        "error": "The limit must be an integer between 1 and 100",
        "codigo": "ENTRADA_INVALIDA",
    }


def test_generar_leccion_sin_usuario_en_ingles(client):
    resp = client.post("/api/v2/lecciones/generar/", json={"nivel_hsk": 1}, headers=EN)

    assert resp.get_json() == {"error": "The field 'usuario_id' is required", "codigo": "ENTRADA_INVALIDA"}


def test_leccion_inexistente_en_ingles(client):
    resp = client.get("/api/v2/lecciones/9999/", headers=EN)

    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Lesson not found."
