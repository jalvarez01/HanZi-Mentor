"""Lecciones: port de services/contenido/lecciones/tests.py y validación de entrada."""

import uuid

import pytest
from sqlalchemy import func, select

from modelos import Ejercicio, Leccion
from servicio import generar_contenido

URL_GENERAR = "/api/v2/lecciones/generar/"
USUARIO = uuid.UUID(int=1)


@pytest.fixture(autouse=True)
def caracteres_hsk1(crear_caracter):
    for hanzi, pinyin, definicion in [("你", "ni3", "tú"), ("好", "hao3", "bueno"), ("我", "wo3", "yo")]:
        crear_caracter(hanzi, nivel_hsk=1, pinyin=pinyin, definicion=definicion)


@pytest.fixture
def leccion(sesion):
    leccion = Leccion(usuario_id=USUARIO, nivel_hsk=1)
    sesion.add(leccion)
    sesion.flush()
    return leccion


def test_generar_contenido_crea_ejercicios_del_nivel(sesion, leccion):
    """La entidad Leccion organiza Caracter y Ejercicio vía generarContenido()."""
    ejercicios = leccion.generarContenido(sesion, cantidad=5)
    sesion.commit()

    assert len(ejercicios) > 0
    guardados = sesion.scalar(
        select(func.count()).select_from(Ejercicio).where(Ejercicio.leccion_id == leccion.id)
    )
    assert guardados == len(ejercicios)
    for ejercicio in ejercicios:
        assert ejercicio.tipo in ["trazo", "significado"]
        assert ejercicio.caracter.nivel_hsk == 1


def test_generar_contenido_no_mezcla_otros_niveles(sesion, leccion, crear_caracter):
    """Un carácter clasificado en otro nivel nunca debe aparecer en esta lección."""
    crear_caracter("经", nivel_hsk=3, pinyin="jing1", definicion="pasar")
    crear_caracter("哲", nivel_hsk=5, pinyin="zhe2", definicion="filosofía")

    ejercicios = leccion.generarContenido(sesion, cantidad=10)

    for ejercicio in ejercicios:
        assert ejercicio.caracter.nivel_hsk not in (3, 5)


def test_generar_contenido_prioriza_nivel_exacto_sobre_sin_clasificar(sesion, leccion, crear_caracter):
    """Los caracteres sin clasificar solo rellenan si faltan del nivel exacto."""
    crear_caracter("爱", nivel_hsk=None, pinyin="ai4", definicion="amar")

    ejercicios = leccion.generarContenido(sesion, cantidad=3)

    assert len(ejercicios) == 3
    for ejercicio in ejercicios:
        assert ejercicio.caracter.nivel_hsk == 1


def test_generar_contenido_rellena_con_sin_clasificar_si_faltan(sesion, leccion, crear_caracter):
    """Si el nivel exacto no alcanza para `cantidad`, se completa con nivel_hsk NULL."""
    crear_caracter("爱", nivel_hsk=None, pinyin="ai4", definicion="amar")
    crear_caracter("心", nivel_hsk=None, pinyin="xin1", definicion="corazón")

    ejercicios = leccion.generarContenido(sesion, cantidad=5)

    niveles = [ejercicio.caracter.nivel_hsk for ejercicio in ejercicios]
    assert len(ejercicios) == 5
    assert niveles.count(1) == 3
    assert niveles.count(None) == 2


def test_generar_contenido_respeta_excluir(sesion, leccion):
    ejercicios = generar_contenido(sesion, leccion, cantidad=5, excluir=["你"])

    assert sorted(e.caracter.hanzi for e in ejercicios) == ["好", "我"]


def test_endpoint_generar_leccion_devuelve_201(client):
    resp = client.post(URL_GENERAR, json={"usuario_id": 1, "nivel_hsk": 1, "cantidad": 5})

    assert resp.status_code == 201
    datos = resp.get_json()
    assert len(datos["ejercicios"]) > 0
    assert datos["usuario_id"] == "00000000-0000-0000-0000-000000000001"
    assert datos["creada_en"].endswith("Z")


def test_endpoint_generar_leccion_acepta_uuid_y_cantidad_por_defecto(client):
    usuario = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

    resp = client.post(URL_GENERAR, json={"usuario_id": usuario, "nivel_hsk": "1"})

    assert resp.status_code == 201
    assert resp.get_json()["usuario_id"] == usuario
    assert len(resp.get_json()["ejercicios"]) == 3


def test_endpoint_generar_leccion_nivel_invalido_devuelve_400(client):
    resp = client.post(URL_GENERAR, json={"usuario_id": 1, "nivel_hsk": 9})

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


@pytest.mark.parametrize("cuerpo", [
    {"nivel_hsk": 1},
    {"usuario_id": "no-es-uuid", "nivel_hsk": 1},
    {"usuario_id": True, "nivel_hsk": 1},
    {"usuario_id": 1},
    {"usuario_id": 1, "nivel_hsk": 0},
    {"usuario_id": 1, "nivel_hsk": 1.5},
    {"usuario_id": 1, "nivel_hsk": 1, "cantidad": 0},
    {"usuario_id": 1, "nivel_hsk": 1, "cantidad": 51},
    [1, 2],
])
def test_endpoint_generar_leccion_entrada_invalida_devuelve_400(client, cuerpo):
    resp = client.post(URL_GENERAR, json=cuerpo)

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_endpoint_generar_leccion_sin_json_devuelve_400(client):
    resp = client.post(URL_GENERAR, data="no es json", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_endpoint_detalle_leccion_inexistente_devuelve_404(client):
    resp = client.get("/api/v2/lecciones/9999/")

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Lección no encontrada.", "codigo": "NO_ENCONTRADO"}


def test_endpoint_detalle_leccion_devuelve_200(client, sesion, leccion):
    leccion.generarContenido(sesion, cantidad=5)
    sesion.commit()

    resp = client.get(f"/api/v2/lecciones/{leccion.id}/")

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["id"] == leccion.id
    ids = [e["id"] for e in datos["ejercicios"]]
    assert len(ids) == 3
    assert ids == sorted(ids)
