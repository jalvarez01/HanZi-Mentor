"""Reto de pinyin para el equipo aliado: GET /api/v2/publico/reto/ y
POST /api/v2/publico/reto/responder/."""

import random

import pytest

import publico

URL = "/api/v2/publico/reto/"
RESPONDER = "/api/v2/publico/reto/responder/"
EN = {"Accept-Language": "en"}


@pytest.fixture
def catalogo(crear_caracter):
    crear_caracter("长", nivel_hsk=1, pinyin="zhǎng", lecturas=["zhǎng", "cháng"], definicion="long; grow")
    crear_caracter("常", nivel_hsk=1, pinyin="cháng", definicion="often")
    crear_caracter("人", nivel_hsk=1, pinyin="rén", definicion="man; people")
    crear_caracter("大", nivel_hsk=1, pinyin="dà", definicion="big")
    crear_caracter("水", nivel_hsk=1, pinyin="shuǐ", definicion="water")
    crear_caracter("学", nivel_hsk=2, pinyin="xué", definicion="learn")


# --- El reto ---

def test_reto_con_4_opciones_distintas_y_la_correcta(client, catalogo):
    resp = client.get(URL, query_string={"nivel": 1})

    assert resp.status_code == 200
    datos = resp.get_json()
    assert list(datos) == ["hanzi", "nivel_hsk", "pregunta", "opciones"]
    assert datos["nivel_hsk"] == 1
    assert len(datos["opciones"]) == 4
    assert len(set(datos["opciones"])) == 4
    correctas = {"长": "zhǎng", "常": "cháng", "人": "rén", "大": "dà", "水": "shuǐ"}
    assert correctas[datos["hanzi"]] in datos["opciones"]


def test_ninguna_opcion_falsa_es_otra_lectura_del_caracter(sesion, catalogo):
    # 长 también se lee "cháng", que es el pinyin de 常: no puede ser opción falsa.
    for semilla in range(30):
        datos = publico.reto(sesion, 1, random.Random(semilla))
        if datos["hanzi"] == "长":
            assert "cháng" not in datos["opciones"]
            assert "zhǎng" in datos["opciones"]


def test_el_filtro_por_nivel(client, catalogo):
    datos = client.get(URL, query_string={"nivel": 2}).get_json()

    # En el nivel 2 hay un solo carácter: no hay opciones falsas posibles.
    assert datos["hanzi"] == "学"
    assert datos["opciones"] == ["xué"]


def test_sin_nivel_elige_entre_todos(client, catalogo):
    assert client.get(URL).get_json()["hanzi"] in {"长", "常", "人", "大", "水", "学"}


def test_nivel_sin_caracteres_da_404(client, catalogo):
    resp = client.get(URL, query_string={"nivel": 6, "lang": "en"})

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "There are no characters for that level.", "codigo": "NO_ENCONTRADO"}


def test_nivel_invalido_da_400(client, catalogo):
    resp = client.get(URL, query_string={"nivel": 9})

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_la_pregunta_en_el_idioma_pedido(client, catalogo):
    es = client.get(URL, query_string={"nivel": 2}).get_json()["pregunta"]
    con_lang = client.get(URL, query_string={"nivel": 2, "lang": "en"}).get_json()["pregunta"]
    con_cabecera = client.get(URL, query_string={"nivel": 2}, headers=EN).get_json()["pregunta"]

    assert es == "¿Cómo se lee 学?"
    assert con_lang == con_cabecera == "How do you read 学?"


# --- Responder ---

def responder(client, hanzi, respuesta, **kwargs):
    return client.post(RESPONDER, json={"hanzi": hanzi, "respuesta": respuesta}, **kwargs)


def test_respuesta_correcta(client, catalogo):
    resp = responder(client, "人", "rén")

    assert resp.status_code == 200
    assert resp.get_json() == {
        "hanzi": "人",
        "respuesta": "rén",
        "correcta": True,
        "pinyin": "rén",
        "lecturas": ["rén"],
        "definicion": "man; people",
    }


def test_respuesta_incorrecta_trae_la_correcta(client, catalogo):
    datos = responder(client, "人", "dà").get_json()

    assert datos["correcta"] is False
    assert datos["pinyin"] == "rén"


def test_cualquier_lectura_vale(client, catalogo):
    assert responder(client, "长", "cháng").get_json()["correcta"] is True
    assert responder(client, "长", "zhǎng").get_json()["correcta"] is True


def test_el_tono_cuenta(client, catalogo):
    # Es de selección múltiple: "ren" sin tono no es ninguna de las opciones.
    assert responder(client, "人", "ren").get_json()["correcta"] is False


def test_mayusculas_y_espacios_no_cuentan(client, catalogo):
    assert responder(client, "人", "  RÉN ").get_json()["correcta"] is True


def test_caracter_que_no_existe_da_404(client, catalogo):
    resp = client.post(RESPONDER + "?lang=en", json={"hanzi": "龍", "respuesta": "lóng"})

    assert resp.status_code == 404
    assert resp.get_json()["codigo"] == "NO_ENCONTRADO"


@pytest.mark.parametrize(
    "cuerpo, mensaje",
    [
        (None, "The body must be a JSON object"),
        ({"respuesta": "rén"}, "The field 'hanzi' is required and must be text"),
        ({"hanzi": "人", "respuesta": "  "}, "The field 'respuesta' is required and must be text"),
        ({"hanzi": "人人人人人", "respuesta": "rén"}, "The field 'hanzi' allows up to 4 characters"),
        ({"hanzi": "人", "respuesta": "r" * 31}, "The field 'respuesta' allows up to 30 characters"),
    ],
)
def test_entrada_invalida_en_ingles(client, catalogo, cuerpo, mensaje):
    resp = client.post(RESPONDER, json=cuerpo, headers=EN)

    assert resp.status_code == 400
    assert resp.get_json() == {"error": mensaje, "codigo": "ENTRADA_INVALIDA"}


# --- CORS ---

def test_cors_en_el_reto_y_en_la_respuesta(client, catalogo):
    assert client.get(URL).headers["Access-Control-Allow-Origin"] == "*"
    assert responder(client, "人", "rén").headers["Access-Control-Allow-Origin"] == "*"


def test_peticion_previa_del_navegador_para_el_post(client, catalogo):
    resp = client.options(
        RESPONDER,
        headers={
            "Origin": "http://vaultdrop.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in resp.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in resp.headers["Access-Control-Allow-Headers"]
