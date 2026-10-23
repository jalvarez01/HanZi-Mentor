"""GET /api/v2/caracteres/ y GET /api/v2/caracteres/<hanzi>/."""

import pytest

URL = "/api/v2/caracteres/"


def hanzi_de(resp):
    return [c["hanzi"] for c in resp.get_json()["caracteres"]]


@pytest.fixture
def catalogo(crear_caracter):
    crear_caracter("人", nivel_hsk=1, pinyin="rén", definicion="persona", frecuencia=2)
    crear_caracter("大", nivel_hsk=1, pinyin="dà", definicion="grande", frecuencia=1)
    crear_caracter("学", nivel_hsk=2, pinyin="xué", definicion="estudiar")
    crear_caracter("校", nivel_hsk=2, pinyin="xiào", definicion="escuela")
    crear_caracter("爱", nivel_hsk=None, pinyin="ài", definicion="amar")


def test_lista_filtra_por_nivel(client, catalogo):
    resp = client.get(URL, query_string={"nivel": 2})

    assert resp.status_code == 200
    assert sorted(hanzi_de(resp)) == ["学", "校"]


def test_lista_excluye_caracteres(client, catalogo):
    resp = client.get(URL, query_string={"nivel": 2, "excluir": "学,"})

    assert hanzi_de(resp) == ["校"]


def test_lista_respeta_el_limite(client, catalogo):
    assert len(hanzi_de(client.get(URL, query_string={"limite": 2}))) == 2


def test_lista_ordena_por_nivel_y_frecuencia_sin_clasificar_al_final(client, catalogo):
    assert hanzi_de(client.get(URL)) == ["大", "人", "学", "校", "爱"]


def test_lista_limite_por_defecto_es_20(client, crear_caracter):
    for i in range(25):
        crear_caracter(chr(0x4E00 + i))

    assert len(hanzi_de(client.get(URL))) == 20


def test_lista_vacia_si_no_hay_del_nivel(client, catalogo):
    resp = client.get(URL, query_string={"nivel": 6})

    assert resp.status_code == 200
    assert resp.get_json() == {"caracteres": []}


@pytest.mark.parametrize("limite", ["abc", "0", "-1", "101", "2.5", ""])
def test_limite_invalido_devuelve_400(client, limite):
    resp = client.get(URL, query_string={"limite": limite})

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"
    assert "límite" in resp.get_json()["error"]


def test_nivel_no_numerico_devuelve_400(client):
    resp = client.get(URL, query_string={"nivel": "uno"})

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_detalle_incluye_trazos_en_orden(client, crear_caracter):
    crear_caracter("人", pinyin="rén", definicion="persona", radical="人", trazos=2)

    resp = client.get(f"{URL}人/")

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["hanzi"] == "人"
    assert datos["radical"] == "人"
    assert [t["secuencia"] for t in datos["trazos"]] == [1, 2]
    assert datos["trazos"][0]["path_svg"] == "M 1 0 L 1 10"
    assert datos["trazos"][0]["mediana"] == [[458, 800], [435, 764], [400, 700], [350, 620], [300, 540]]


def test_detalle_responde_hanzi_legible(client, crear_caracter):
    crear_caracter("人")

    assert "人" in client.get(f"{URL}人/").get_data(as_text=True)


def test_detalle_inexistente_devuelve_404(client):
    resp = client.get(f"{URL}不/")

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Carácter no encontrado.", "codigo": "NO_ENCONTRADO"}
