"""Trazo fuera de lugar: se decide antes que el sentido y el largo.

Medianas reales de 人 y 大 (Make Me a Hanzi). El temblor es determinista:
deriva lenta más ruido punto a punto, con semilla fija. Lienzo de 300 px,
como en el móvil. Los valores de UMBRAL_FUERA_DE_LUGAR se explican en
comparador.py.
"""

import random

import pytest

from app import create_app
from comparador import comparar_trazo

MEDIANAS = {
    "人 1": [[483, 736], [508, 702], [511, 678], [473, 552], [408, 416], [328, 303], [271, 244], [144, 139], [72, 95]],
    "人 2": [[474, 477], [477, 459], [490, 439], [571, 333], [691, 200], [753, 145], [798, 119], [986, 90]],
    "大 1": [[210, 458], [268, 453], [514, 503], [719, 534], [770, 529], [810, 517]],
    "大 2": [[416, 810], [444, 799], [482, 759], [469, 518], [448, 394], [426, 320], [386, 231], [361, 196],
             [307, 140], [202, 67], [138, 41]],
    "大 3": [[486, 430], [500, 393], [576, 284], [660, 182], [722, 118], [774, 77], [953, 42]],
}
LADO = 300
URL = "/api/v2/trazos/validar/"
CENTRO = [[LADO * 0.3, LADO * 0.5], [LADO * 0.7, LADO * 0.5]]


def a_canvas(punto):
    x, y = punto
    return [x / 1024 * LADO, (900 - y) / 1024 * LADO]


def densificar(puntos, por_segmento=25):
    resultado = []
    for a, b in zip(puntos, puntos[1:]):
        for t in range(por_segmento):
            f = t / por_segmento
            resultado.append([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f])
    resultado.append(list(puntos[-1]))
    return resultado


def con_temblor(puntos, px, semilla):
    azar = random.Random(semilla)
    dx = dy = 0.0
    salida = []
    for x, y in puntos:
        dx = 0.9 * dx + azar.gauss(0, px * 0.5)
        dy = 0.9 * dy + azar.gauss(0, px * 0.5)
        salida.append([x + dx + azar.gauss(0, px), y + dy + azar.gauss(0, px)])
    return salida


def dibujo(mediana):
    return densificar([a_canvas(p) for p in mediana])


def motivo(puntos, mediana):
    return comparar_trazo(puntos, mediana, LADO, LADO).motivo


@pytest.mark.parametrize("px", [2, 4, 6])
@pytest.mark.parametrize("nombre", MEDIANAS)
def test_un_trazo_correcto_con_temblor_nunca_esta_fuera_de_lugar(nombre, px):
    mediana = MEDIANAS[nombre]
    motivos = {motivo(con_temblor(dibujo(mediana), px, semilla), mediana) for semilla in range(20)}

    assert "fuera_de_lugar" not in motivos
    assert motivos == {"correcto"}


@pytest.mark.parametrize("nombre", MEDIANAS)
def test_un_trazo_algo_desplazado_sigue_siendo_impreciso(nombre):
    # Un 8 % del lienzo en diagonal: en su lugar, pero corrido.
    mediana = MEDIANAS[nombre]
    corrido = [[x + 0.08 * 1024, y - 0.08 * 1024] for x, y in mediana]
    motivos = [motivo(con_temblor(dibujo(corrido), 2, semilla), mediana) for semilla in range(10)]

    assert "fuera_de_lugar" not in motivos
    assert set(motivos) <= {"impreciso", "correcto"}
    assert "impreciso" in motivos


@pytest.mark.parametrize("nombre", MEDIANAS)
def test_una_linea_en_el_centro_del_lienzo_esta_fuera_de_lugar(nombre):
    assert motivo(densificar(CENTRO, 60), MEDIANAS[nombre]) == "fuera_de_lugar"


@pytest.mark.parametrize("dibujado, esperado", [("人 2", "人 1"), ("人 1", "人 2"), ("大 3", "大 1"), ("大 1", "大 2")])
def test_otro_trazo_del_caracter_esta_fuera_de_lugar(dibujado, esperado):
    assert motivo(dibujo(MEDIANAS[dibujado]), MEDIANAS[esperado]) == "fuera_de_lugar"


def test_una_linea_en_la_esquina_contraria_esta_fuera_de_lugar():
    esquina = densificar([[LADO * 0.6, LADO * 0.7], [LADO * 0.95, LADO * 0.97]], 60)

    assert motivo(esquina, MEDIANAS["人 1"]) == "fuera_de_lugar"


def test_corto_largo_e_invertido_en_su_lugar_no_cambian():
    mediana = MEDIANAS["人 1"]
    denso = densificar([a_canvas(p) for p in mediana], 20)

    assert motivo(denso[: len(denso) * 4 // 10], mediana) == "incompleto"
    assert motivo(dibujo(mediana + mediana[::-1][1:] + mediana[1:]), mediana) == "incompleto"
    assert motivo(dibujo(list(reversed(mediana))), mediana) == "invertido"


def test_una_linea_en_el_centro_no_se_da_por_invertida_ni_corta():
    # El caso que motivó el cambio: antes daba "incompleto" (o "invertido",
    # con "la forma es correcta").
    resultado = comparar_trazo(densificar(CENTRO, 60), MEDIANAS["人 1"], LADO, LADO)

    assert resultado.motivo == "fuera_de_lugar"
    assert resultado.invertido is False
    assert resultado.aprobado is False
    assert resultado.puntaje <= 20


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


def test_fuera_de_lugar_por_la_api_en_espanol_y_en_ingles(client):
    cuerpo = {"mediana": MEDIANAS["人 1"], "puntos": densificar(CENTRO, 60), "ancho": LADO, "alto": LADO}

    es = client.post(URL, json=cuerpo).get_json()
    en = client.post(URL, json=cuerpo, headers={"Accept-Language": "en"}).get_json()

    assert es["motivo"] == en["motivo"] == "fuera_de_lugar"
    assert es["aprobado"] is False and es["invertido"] is False
    assert es["puntaje"] <= 20
    assert es["detalle"] == "Trazo fuera de lugar. Intentá de nuevo."
    assert en["detalle"] == "Stroke out of place. Try again."
