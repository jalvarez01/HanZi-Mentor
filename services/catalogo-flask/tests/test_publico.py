"""T14: GET /api/v2/publico/resumen/, el servicio que consume el equipo aliado."""

from datetime import date, datetime, timedelta, timezone

import pytest

import publico

URL = "/api/v2/publico/resumen/"
EN = {"Accept-Language": "en"}


@pytest.fixture
def catalogo(crear_caracter):
    crear_caracter("人", nivel_hsk=1, pinyin="rén", definicion="man; people", frecuencia=2)
    crear_caracter("大", nivel_hsk=1, pinyin="dà", definicion="big", frecuencia=1)
    crear_caracter("学", nivel_hsk=2, pinyin="xué", definicion="learn")
    crear_caracter("校", nivel_hsk=2, pinyin="xiào", definicion="school")
    crear_caracter("爱", nivel_hsk=None, pinyin="ài", definicion="love")


# --- Respuesta ---

def test_resumen_con_totales_por_nivel(client, catalogo):
    resp = client.get(URL)

    assert resp.status_code == 200
    datos = resp.get_json()
    assert list(datos) == [
        "sistema", "caracteres_totales", "por_nivel_hsk", "caracter_del_dia", "generado_en",
    ]
    assert datos["sistema"] == "HanziMentor"
    # El total incluye los caracteres sin nivel HSK; por nivel, solo los clasificados.
    assert datos["caracteres_totales"] == 5
    assert datos["por_nivel_hsk"] == {"1": 2, "2": 2, "3": 0, "4": 0, "5": 0, "6": 0}


def test_caracter_del_dia_tiene_nivel_y_sus_datos(client, catalogo):
    caracter = client.get(URL).get_json()["caracter_del_dia"]

    assert caracter["hanzi"] in {"人", "大", "学", "校"}
    assert set(caracter) == {"hanzi", "pinyin", "definicion", "nivel_hsk"}
    assert caracter["nivel_hsk"] is not None


def test_generado_en_es_una_fecha_iso_en_utc(client, catalogo):
    generado = client.get(URL).get_json()["generado_en"]

    assert generado.endswith("Z")
    assert datetime.strptime(generado, "%Y-%m-%dT%H:%M:%SZ")


def test_filtro_por_nivel_elige_el_caracter_de_ese_nivel(client, catalogo):
    datos = client.get(URL, query_string={"nivel": 2}).get_json()

    assert datos["caracter_del_dia"]["hanzi"] in {"学", "校"}
    # Los totales no cambian con el filtro.
    assert datos["caracteres_totales"] == 5


def test_nivel_sin_caracteres_devuelve_caracter_del_dia_null(client, catalogo):
    assert client.get(URL, query_string={"nivel": 6}).get_json()["caracter_del_dia"] is None


def test_catalogo_vacio(client):
    datos = client.get(URL).get_json()

    assert datos["caracteres_totales"] == 0
    assert set(datos["por_nivel_hsk"].values()) == {0}
    assert datos["caracter_del_dia"] is None


# --- Carácter del día ---

def test_mismo_caracter_durante_todo_el_dia(sesion, catalogo):
    manana = datetime(2026, 10, 26, 0, 5, tzinfo=timezone.utc)
    noche = datetime(2026, 10, 26, 23, 55, tzinfo=timezone.utc)

    assert (
        publico.resumen(sesion, ahora=manana)["caracter_del_dia"]
        == publico.resumen(sesion, ahora=noche)["caracter_del_dia"]
    )


def test_cambia_de_un_dia_al_siguiente(sesion, catalogo):
    hoy = date(2026, 10, 26)

    caracteres = {
        publico.caracter_del_dia(sesion, hoy + timedelta(days=n))["hanzi"] for n in range(4)
    }

    # Con 4 caracteres clasificados, 4 días seguidos los recorren todos.
    assert caracteres == {"人", "大", "学", "校"}


# --- Validación y errores ---

@pytest.mark.parametrize("nivel", ["abc", "0", "7", "-1"])
def test_nivel_invalido_responde_400(client, catalogo, nivel):
    resp = client.get(URL, query_string={"nivel": nivel})

    assert resp.status_code == 400
    assert resp.get_json() == {
        "error": "El campo 'nivel' debe ser un entero entre 1 y 6",
        "codigo": "ENTRADA_INVALIDA",
    }


def test_error_en_ingles_con_accept_language(client, catalogo):
    resp = client.get(URL, query_string={"nivel": "7"}, headers=EN)

    assert resp.get_json()["error"] == "The field 'nivel' must be an integer between 1 and 6"


def test_solo_acepta_get(client):
    resp = client.post(URL)

    assert resp.status_code == 405
    assert resp.get_json()["codigo"] == "METODO_NO_PERMITIDO"


# --- CORS ---

def test_permite_cualquier_origen(client, catalogo):
    assert client.get(URL).headers["Access-Control-Allow-Origin"] == "*"


def test_permite_cualquier_origen_tambien_en_errores(client, catalogo):
    resp = client.get(URL, query_string={"nivel": "abc"})

    assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_las_demas_rutas_no_abren_cors(client, catalogo):
    assert "Access-Control-Allow-Origin" not in client.get("/api/v2/caracteres/").headers
