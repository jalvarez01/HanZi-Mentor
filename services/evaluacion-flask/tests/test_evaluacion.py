"""POST /api/v2/evaluacion/: cada tipo, validación, 404 y 503.

Incluye el port de EvaluarEjercicioServiceTest y EvaluarRespuestaTrazoTest
de agente-tutor/tutor/tests.py.
"""

import pytest

from conftest import MEDIANA_1, CatalogoFalso, TrazosFalso
from app import create_app
from fabricas import Dependencias

TRAZO_OK = {"secuencia": 1, "puntos": [[0, 0], [1, 1]], "ancho": 320, "alto": 320}


def assert_error(resp, estado, codigo):
    assert resp.status_code == estado, resp.get_data(as_text=True)
    assert resp.is_json
    datos = resp.get_json()
    assert datos["codigo"] == codigo
    assert isinstance(datos["error"], str) and datos["error"]
    return datos


def cliente_con(catalogo=None, trazos=None):
    deps = Dependencias(catalogo=catalogo or CatalogoFalso(), trazos=trazos or TrazosFalso())
    return create_app({"TESTING": True}, dependencias=deps).test_client()


# ------------------------------------------------------------------ pinyin


def test_evalua_pinyin_correctamente(evaluar, catalogo):
    resp = evaluar(tipo="pinyin", caracter="学", respuesta="xue")

    assert resp.status_code == 200
    assert resp.get_json() == {"tipo": "pinyin", "caracter": "学", "acerto": True}
    assert catalogo.consultas == ["学"]


def test_pinyin_incorrecto(evaluar):
    resp = evaluar(tipo="pinyin", caracter="学", respuesta="xiao")

    assert resp.status_code == 200
    assert resp.get_json()["acerto"] is False


def test_pinyin_no_llama_a_trazos(evaluar, trazos):
    evaluar(tipo="pinyin", caracter="学", respuesta="xué")

    assert trazos.llamadas == []


# ------------------------------------------------------------- significado


def test_evalua_significado_incorrectamente(evaluar):
    resp = evaluar(tipo="significado", caracter="学", respuesta="mountain")

    assert resp.status_code == 200
    assert resp.get_json() == {"tipo": "significado", "caracter": "学", "acerto": False}


def test_significado_correcto_en_otro_orden(evaluar):
    resp = evaluar(tipo="significado", caracter="学", respuesta="learning, study")

    assert resp.get_json()["acerto"] is True


def test_la_dificultad_cambia_el_umbral():
    catalogo = CatalogoFalso({"学": {"hanzi": "学", "definicion": "aprender", "trazos": []}})
    client = cliente_con(catalogo=catalogo)
    cuerpo = {"tipo": "significado", "caracter": "学", "respuesta": "aprendio"}

    facil = client.post("/api/v2/evaluacion/", json={**cuerpo, "dificultad": 1})
    dificil = client.post("/api/v2/evaluacion/", json={**cuerpo, "dificultad": 5})

    assert facil.get_json()["acerto"] is True
    assert dificil.get_json()["acerto"] is False


def test_dificultad_por_defecto_es_3():
    catalogo = CatalogoFalso({"学": {"hanzi": "学", "definicion": "aprender", "trazos": []}})
    client = cliente_con(catalogo=catalogo)

    cuerpo = {"tipo": "significado", "caracter": "学", "respuesta": "aprendio"}

    # "aprendio" vs "aprender" da 0.75: justo el umbral de dificultad 3,
    # por debajo del de dificultad 4.
    sin = client.post("/api/v2/evaluacion/", json=cuerpo)
    con_4 = client.post("/api/v2/evaluacion/", json={**cuerpo, "dificultad": 4})

    assert sin.get_json()["acerto"] is True
    assert con_4.get_json()["acerto"] is False


# ------------------------------------------------------------------- trazo


def test_evalua_trazo_delegando_en_trazos(evaluar, trazos):
    resp = evaluar(tipo="trazo", caracter="学", respuesta=TRAZO_OK)

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["acerto"] is True
    assert datos["aprobado"] is True
    assert datos["puntaje"] == 92
    # La mediana sale del catálogo, según la secuencia pedida.
    assert trazos.llamadas == [
        {"mediana": MEDIANA_1, "puntos": [[0, 0], [1, 1]], "ancho": 320, "alto": 320}
    ]


def test_evalua_trazo_devuelve_resultado_completo():
    veredicto = {
        "aprobado": False,
        "puntaje": 40,
        "motivo": "forma_distinta",
        "detalle": "trazo invertido",
        "invertido": True,
        "puntos_lejanos": [{"posicion": 1.0, "desvio": 0.6}],
    }
    trazos = TrazosFalso(veredicto)
    client = cliente_con(trazos=trazos)

    resp = client.post(
        "/api/v2/evaluacion/",
        json={"tipo": "trazo", "caracter": "学",
              "respuesta": {"secuencia": 2, "puntos": [[0, 0], [5, 5]], "ancho": 320, "alto": 320}},
    )

    datos = resp.get_json()
    assert list(datos) == [
        "tipo", "caracter", "acerto", "secuencia",
        "aprobado", "puntaje", "motivo", "invertido", "detalle", "puntos_lejanos",
    ]
    assert datos["acerto"] is False
    assert datos["secuencia"] == 2
    assert datos["motivo"] == "forma_distinta"
    assert datos["invertido"] is True
    assert trazos.llamadas[0]["mediana"] == [[10, 10], [20, 20]]


def test_trazo_sin_secuencia_es_400(evaluar, trazos):
    sin_secuencia = {k: v for k, v in TRAZO_OK.items() if k != "secuencia"}

    datos = assert_error(evaluar(tipo="trazo", caracter="学", respuesta=sin_secuencia), 400, "ENTRADA_INVALIDA")

    assert "secuencia" in datos["error"]
    assert trazos.llamadas == []


def test_trazo_con_secuencia_inexistente_es_404(evaluar, trazos):
    datos = assert_error(
        evaluar(tipo="trazo", caracter="学", respuesta={**TRAZO_OK, "secuencia": 9}),
        404, "NO_ENCONTRADO",
    )

    assert datos["error"] == "El carácter '学' no tiene un trazo con secuencia 9."
    assert trazos.llamadas == []


def test_trazo_sin_mediana_en_el_catalogo_es_404():
    catalogo = CatalogoFalso({"学": {"hanzi": "学", "trazos": [{"secuencia": 1, "mediana": None}]}})

    resp = cliente_con(catalogo=catalogo).post(
        "/api/v2/evaluacion/", json={"tipo": "trazo", "caracter": "学", "respuesta": TRAZO_OK}
    )

    assert_error(resp, 404, "NO_ENCONTRADO")


def test_puntos_rechazados_por_trazos_es_400_con_su_mensaje():
    trazos = TrazosFalso(rechazo={"error": "'puntos' necesita al menos 2 puntos", "codigo": "ENTRADA_INVALIDA"})

    resp = cliente_con(trazos=trazos).post(
        "/api/v2/evaluacion/",
        json={"tipo": "trazo", "caracter": "学", "respuesta": {**TRAZO_OK, "puntos": [[0, 0]]}},
    )

    datos = assert_error(resp, 400, "ENTRADA_INVALIDA")
    assert datos["error"] == "'puntos' necesita al menos 2 puntos"


# ------------------------------------------------------------- validación


@pytest.mark.parametrize("cuerpo, fragmento", [
    ({"caracter": "学", "respuesta": "xue"}, "tipo"),
    ({"tipo": "pinyin", "respuesta": "xue"}, "caracter"),
    ({"tipo": "pinyin", "caracter": "学"}, "respuesta"),
    ({"tipo": "audio", "caracter": "学", "respuesta": "xue"}, "tipo"),
    ({"tipo": "pinyin", "caracter": "", "respuesta": "xue"}, "caracter"),
    ({"tipo": "pinyin", "caracter": 5, "respuesta": "xue"}, "caracter"),
    ({"tipo": "pinyin", "caracter": "学" * 9, "respuesta": "xue"}, "caracter"),
    ({"tipo": "pinyin", "caracter": "学", "respuesta": 5}, "respuesta"),
    ({"tipo": "pinyin", "caracter": "学", "respuesta": "x" * 201}, "respuesta"),
    ({"tipo": "significado", "caracter": "学", "respuesta": "a", "dificultad": 6}, "dificultad"),
    ({"tipo": "significado", "caracter": "学", "respuesta": "a", "dificultad": 0}, "dificultad"),
    ({"tipo": "significado", "caracter": "学", "respuesta": "a", "dificultad": True}, "dificultad"),
    ({"tipo": "significado", "caracter": "学", "respuesta": "a", "dificultad": "3"}, "dificultad"),
    ({"tipo": "trazo", "caracter": "学", "respuesta": "xue"}, "respuesta"),
    ({"tipo": "trazo", "caracter": "学", "respuesta": {**TRAZO_OK, "secuencia": 0}}, "secuencia"),
    ({"tipo": "trazo", "caracter": "学", "respuesta": {**TRAZO_OK, "secuencia": True}}, "secuencia"),
    ({"tipo": "trazo", "caracter": "学", "respuesta": {**TRAZO_OK, "puntos": "nada"}}, "puntos"),
    ({"tipo": "trazo", "caracter": "学", "respuesta": {**TRAZO_OK, "ancho": -1}}, "ancho"),
    ({"tipo": "trazo", "caracter": "学", "respuesta": {**TRAZO_OK, "alto": 1.5}}, "alto"),
])
def test_entrada_invalida_es_400(evaluar, catalogo, cuerpo, fragmento):
    datos = assert_error(evaluar(**cuerpo), 400, "ENTRADA_INVALIDA")

    assert fragmento in datos["error"]
    # La validación corta antes de consultar otro servicio.
    assert catalogo.consultas == []


def test_cuerpo_que_no_es_json_es_400(client):
    resp = client.post("/api/v2/evaluacion/", data="no es json", content_type="application/json")

    assert_error(resp, 400, "ENTRADA_INVALIDA")


def test_cuerpo_lista_es_400(client):
    assert_error(client.post("/api/v2/evaluacion/", json=[1, 2]), 400, "ENTRADA_INVALIDA")


def test_caracter_con_espacios_se_recorta(evaluar, catalogo):
    resp = evaluar(tipo="pinyin", caracter=" 学 ", respuesta="xue")

    assert resp.get_json()["caracter"] == "学"
    assert catalogo.consultas == ["学"]


# ---------------------------------------------------------------- 404 y 503


def test_caracter_desconocido_es_404(evaluar):
    datos = assert_error(evaluar(tipo="pinyin", caracter="龘", respuesta="da"), 404, "NO_ENCONTRADO")

    assert datos["error"] == "No existe el carácter '龘'."


@pytest.mark.parametrize("tipo, respuesta", [
    ("pinyin", "xue"), ("significado", "study"), ("trazo", TRAZO_OK),
])
def test_catalogo_caido_es_503(tipo, respuesta):
    client = cliente_con(catalogo=CatalogoFalso(caido=True))

    resp = client.post("/api/v2/evaluacion/", json={"tipo": tipo, "caracter": "学", "respuesta": respuesta})

    datos = assert_error(resp, 503, "DEPENDENCIA_NO_DISPONIBLE")
    assert "catálogo" in datos["error"]


def test_trazos_caido_es_503_y_no_adivina():
    client = cliente_con(trazos=TrazosFalso(caido=True))

    resp = client.post("/api/v2/evaluacion/", json={"tipo": "trazo", "caracter": "学", "respuesta": TRAZO_OK})

    datos = assert_error(resp, 503, "DEPENDENCIA_NO_DISPONIBLE")
    assert "trazos" in datos["error"]
    assert "acerto" not in datos


def test_con_trazos_caido_pinyin_sigue_funcionando():
    client = cliente_con(trazos=TrazosFalso(caido=True))

    resp = client.post("/api/v2/evaluacion/", json={"tipo": "pinyin", "caracter": "学", "respuesta": "xue"})

    assert resp.status_code == 200
    assert resp.get_json()["acerto"] is True
